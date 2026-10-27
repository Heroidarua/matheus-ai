"""Optional Google Workspace OAuth integration with encrypted PostgreSQL token storage.

The integration is disabled unless OAuth credentials, a PostgreSQL DATABASE_URL,
and a Fernet encryption key are configured. Only read-only Google scopes are used.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api/google", tags=["google-workspace"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API_ROOT = "https://www.googleapis.com"
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _settings() -> tuple[str, str, str, str]:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    encryption_key = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()
    if not all((client_id, client_secret, database_url, encryption_key)):
        raise HTTPException(
            status_code=503,
            detail=(
                "Integração Google Workspace ainda não configurada. Configure "
                "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, DATABASE_URL "
                "e GOOGLE_TOKEN_ENCRYPTION_KEY no servidor."
            ),
        )
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://") and "+" in database_url.split("://", 1)[0]:
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        Fernet(encryption_key.encode("ascii"))
    except (ValueError, UnicodeError):
        raise HTTPException(status_code=503, detail="GOOGLE_TOKEN_ENCRYPTION_KEY inválida. Gere uma chave Fernet e configure-a no servidor.")
    return client_id, client_secret, database_url, encryption_key


def _database_call(sql: str, params: tuple[Any, ...] = (), *, fetch: bool = False) -> Any:
    _, _, database_url, _ = _settings()
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS google_oauth_tokens ("
                    "session_id TEXT PRIMARY KEY, encrypted_tokens TEXT NOT NULL, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
                )
                cur.execute(sql, params)
                result = cur.fetchone() if fetch else None
            conn.commit()
            return result
    except HTTPException:
        raise
    except Exception as exc:
        # Do not leak database URLs, credentials, or token material to logs/clients.
        print(f"Google token storage failed ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="O armazenamento seguro da integração Google não está disponível.") from exc


def _encrypt_tokens(tokens: dict[str, Any], key: str) -> str:
    return Fernet(key.encode("ascii")).encrypt(json.dumps(tokens).encode("utf-8")).decode("ascii")


def _decrypt_tokens(value: str, key: str) -> dict[str, Any]:
    try:
        result = json.loads(Fernet(key.encode("ascii")).decrypt(value.encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Não foi possível descriptografar as credenciais Google armazenadas.") from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=503, detail="Formato inválido das credenciais Google armazenadas.")
    return result


def _session_id(request: Request, *, create: bool = False) -> str | None:
    value = request.session.get("google_oauth_session")
    if not value and create:
        value = secrets.token_urlsafe(32)
        request.session["google_oauth_session"] = value
    return value


def _redirect_uri() -> str:
    public_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    if not public_url.startswith("https://"):
        raise HTTPException(status_code=503, detail="Configure PUBLIC_APP_URL com a URL HTTPS pública do serviço Render.")
    return public_url + "/api/google/callback"


async def _load_tokens(request: Request) -> tuple[str, dict[str, Any], str]:
    session_id = _session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Conecte sua conta Google primeiro.")
    _, _, _, key = _settings()
    row = await asyncio.to_thread(
        _database_call,
        "SELECT encrypted_tokens FROM google_oauth_tokens WHERE session_id = %s",
        (session_id,),
        fetch=True,
    )
    if not row:
        raise HTTPException(status_code=401, detail="Nenhuma conta Google conectada nesta sessão.")
    return session_id, _decrypt_tokens(row[0], key), key


async def _get_access_token(request: Request) -> str:
    session_id, tokens, key = await _load_tokens(request)
    expires_at = float(tokens.get("expires_at", 0))
    if tokens.get("access_token") and expires_at > time.time() + 60:
        return str(tokens["access_token"])

    refresh_token = str(tokens.get("refresh_token", ""))
    if not refresh_token:
        raise HTTPException(status_code=401, detail="A sessão Google expirou. Desconecte e autorize novamente.")
    client_id, client_secret, _, _ = _settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        response = await client.post(TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if not response.is_success:
        print(f"Google token refresh failed (HTTP {response.status_code})")
        raise HTTPException(status_code=401, detail="Não foi possível renovar a autorização Google. Reconecte sua conta.")
    fresh = response.json()
    tokens.update(fresh)
    tokens["refresh_token"] = refresh_token
    tokens["expires_at"] = time.time() + int(fresh.get("expires_in", 3600))
    await asyncio.to_thread(
        _database_call,
        "INSERT INTO google_oauth_tokens(session_id, encrypted_tokens) VALUES (%s, %s) "
        "ON CONFLICT(session_id) DO UPDATE SET encrypted_tokens = EXCLUDED.encrypted_tokens, updated_at = NOW()",
        (session_id, _encrypt_tokens(tokens, key)),
    )
    return str(tokens["access_token"])


async def _google_get(request: Request, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    access_token = await _get_access_token(request)
    if not path.startswith("/"):
        raise HTTPException(status_code=400, detail="Caminho de API inválido.")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        response = await client.get(
            API_ROOT + path,
            params=params or {},
            headers={"Authorization": "Bearer " + access_token},
        )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="A autorização Google foi recusada. Reconecte sua conta.")
    if not response.is_success:
        print(f"Google Workspace API failed (HTTP {response.status_code}) path={path.split('?')[0][:80]}")
        raise HTTPException(status_code=502, detail="A API Google não conseguiu concluir a solicitação. Confira as APIs ativadas e os escopos autorizados.")
    data = response.json()
    return data if isinstance(data, dict) else {}


@router.get("/status")
async def google_status(request: Request) -> dict[str, Any]:
    if not all(os.getenv(k, "").strip() for k in (
        "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
        "DATABASE_URL", "GOOGLE_TOKEN_ENCRYPTION_KEY",
    )):
        return {"configured": False, "connected": False, "message": "Integração Google Workspace não configurada."}
    session_id = _session_id(request)
    if not session_id:
        return {"configured": True, "connected": False}
    try:
        row = await asyncio.to_thread(
            _database_call,
            "SELECT updated_at FROM google_oauth_tokens WHERE session_id = %s",
            (session_id,),
            fetch=True,
        )
    except HTTPException:
        return {"configured": True, "connected": False, "storage_available": False}
    return {"configured": True, "connected": bool(row), "updated_at": row[0].isoformat() if row else None}


@router.get("/connect")
async def google_connect(request: Request) -> RedirectResponse:
    client_id, _, _, _ = _settings()
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_state_created"] = int(time.time())
    _session_id(request, create=True)
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })
    return RedirectResponse(AUTH_URL + "?" + query, status_code=302)


@router.get("/callback")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    expected = request.session.pop("google_oauth_state", None)
    created = int(request.session.pop("google_oauth_state_created", 0) or 0)
    if error:
        raise HTTPException(status_code=400, detail="A autorização Google foi cancelada ou recusada.")
    if not expected or not state or not secrets.compare_digest(str(expected), state) or time.time() - created > 600:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido ou expirado. Tente conectar novamente.")
    if not code:
        raise HTTPException(status_code=400, detail="O Google não retornou um código de autorização.")

    client_id, client_secret, _, key = _settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        response = await client.post(TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        })
    if not response.is_success:
        print(f"Google OAuth token exchange failed (HTTP {response.status_code})")
        raise HTTPException(status_code=502, detail="Não foi possível concluir a autorização Google.")
    tokens = response.json()
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
    if not tokens.get("access_token"):
        raise HTTPException(status_code=502, detail="O Google não retornou um token de acesso.")
    session_id = _session_id(request, create=True)
    await asyncio.to_thread(
        _database_call,
        "INSERT INTO google_oauth_tokens(session_id, encrypted_tokens) VALUES (%s, %s) "
        "ON CONFLICT(session_id) DO UPDATE SET encrypted_tokens = EXCLUDED.encrypted_tokens, updated_at = NOW()",
        (session_id, _encrypt_tokens(tokens, key)),
    )
    target = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/") + "/"
    return RedirectResponse(target + "?google=connected", status_code=303)


@router.post("/disconnect")
async def google_disconnect(request: Request) -> dict[str, bool]:
    session_id = _session_id(request)
    if not session_id:
        return {"disconnected": True}
    try:
        _, tokens, _ = await _load_tokens(request)
        access_token = str(tokens.get("access_token", ""))
        if access_token:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    await client.post(REVOKE_URL, data={"token": access_token})
            except httpx.HTTPError:
                pass
    except HTTPException as exc:
        if exc.status_code not in (401,):
            raise
    await asyncio.to_thread(
        _database_call,
        "DELETE FROM google_oauth_tokens WHERE session_id = %s",
        (session_id,),
    )
    request.session.pop("google_oauth_session", None)
    return {"disconnected": True}


@router.get("/gmail/messages")
async def google_gmail_messages(request: Request, q: str = "", max_results: int = 10) -> dict[str, Any]:
    max_results = max(1, min(max_results, 25))
    data = await _google_get(request, "/gmail/v1/users/me/messages", {"q": q[:200], "maxResults": max_results})
    return {"messages": data.get("messages", []), "resultSizeEstimate": data.get("resultSizeEstimate", 0)}


@router.get("/drive/files")
async def google_drive_files(request: Request, q: str = "", page_size: int = 10) -> dict[str, Any]:
    page_size = max(1, min(page_size, 25))
    query = "trashed = false"
    if q.strip():
        # Drive q is a query language, not plain-text search; escape apostrophes.
        safe_q = q.strip()[:150].replace("\\", "\\\\").replace("'", "\\'")
        query += f" and name contains '{safe_q}'"
    data = await _google_get(request, "/drive/v3/files", {
        "q": query, "pageSize": page_size, "orderBy": "modifiedTime desc",
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink),nextPageToken",
    })
    return {"files": data.get("files", []), "nextPageToken": data.get("nextPageToken")}


@router.get("/calendar/events")
async def google_calendar_events(request: Request, max_results: int = 10) -> dict[str, Any]:
    max_results = max(1, min(max_results, 25))
    data = await _google_get(request, "/calendar/v3/calendars/primary/events", {
        "maxResults": max_results, "orderBy": "startTime", "singleEvents": "true",
        "timeMin": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return {"events": data.get("items", [])}


@router.get("/docs/{document_id}")
async def google_document(request: Request, document_id: str) -> dict[str, Any]:
    if not document_id or len(document_id) > 200 or not all(c.isalnum() or c in "-_" for c in document_id):
        raise HTTPException(status_code=400, detail="ID de documento inválido.")
    return await _google_get(request, f"/drive/v3/files/{document_id}", {
        "fields": "id,name,mimeType,modifiedTime,webViewLink"
    })


@router.get("/sheets/{spreadsheet_id}")
async def google_spreadsheet(request: Request, spreadsheet_id: str) -> dict[str, Any]:
    if not spreadsheet_id or len(spreadsheet_id) > 200 or not all(c.isalnum() or c in "-_" for c in spreadsheet_id):
        raise HTTPException(status_code=400, detail="ID de planilha inválido.")
    return await _google_get(request, f"/sheets/v4/spreadsheets/{spreadsheet_id}", {
        "includeGridData": "false"
    })
