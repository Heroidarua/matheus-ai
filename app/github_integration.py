from __future__ import annotations

import base64
import os
import re
import secrets
import time
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/github", tags=["GitHub"])

API_ROOT = "https://api.github.com"
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Matheus-AI-GitHub-App",
}


def _config() -> tuple[str, str, str, str]:
    app_id = os.getenv("GITHUB_APP_ID", "").strip()
    slug = os.getenv("GITHUB_APP_SLUG", "").strip()
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
    public_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    if not all((app_id, slug, private_key, public_url, os.getenv("GITHUB_SESSION_SECRET", "").strip())):
        raise HTTPException(
            status_code=503,
            detail="Integração GitHub não configurada. Configure GITHUB_APP_ID, GITHUB_APP_SLUG, GITHUB_APP_PRIVATE_KEY e PUBLIC_APP_URL no servidor.",
        )
    return app_id, slug, private_key, public_url


def _app_jwt() -> str:
    app_id, _, private_key, _ = _config()
    now = int(time.time())
    try:
        return jwt.encode({"iat": now - 60, "exp": now + 8 * 60, "iss": app_id}, private_key, algorithm="RS256")
    except Exception as exc:
        print(f"GitHub App JWT creation failed ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="Não foi possível autenticar o GitHub App. Confira a chave privada configurada.")


async def _github_request(method: str, path: str, *, token: str | None = None, json_body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = dict(API_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.request(method, API_ROOT + path, headers=headers, json=json_body, params=params)
    except httpx.HTTPError as exc:
        print(f"GitHub API connection failed ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível conectar à API do GitHub.")
    if response.status_code >= 400:
        detail = "A API do GitHub recusou a solicitação."
        try:
            detail = str(response.json().get("message") or detail)
        except (ValueError, AttributeError):
            pass
        print(f"GitHub API HTTP {response.status_code}: {detail[:250]}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repositório/arquivo não encontrado ou não autorizado para este aplicativo.")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=403, detail="A instalação do GitHub não tem as permissões necessárias ou foi removida. Reinstale/autorize o aplicativo.")
        if response.status_code == 422:
            raise HTTPException(status_code=409, detail=f"O GitHub não aceitou a alteração: {detail[:250]}")
        raise HTTPException(status_code=502, detail=f"Erro da API do GitHub ({response.status_code}): {detail[:250]}")
    if response.status_code == 204 or not response.content:
        return {}
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"items": data}
    except ValueError:
        return {}


async def _installation_token(installation_id: int, repository: str | None = None, write: bool = False) -> str:
    body: dict[str, Any] = {"permissions": {"contents": "write" if write else "read"}}
    if repository:
        body["repositories"] = [repository]
    data = await _github_request(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        token=_app_jwt(),
        json_body=body,
    )
    token = data.get("token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=502, detail="O GitHub não retornou um token de instalação válido.")
    return token


def _installation_id(request: Request) -> int:
    value = request.session.get("github_installation_id")
    if not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=401, detail="Conecte primeiro uma instalação do GitHub.")
    return value


def _selected_repo(request: Request) -> str:
    repo = request.session.get("github_selected_repo")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise HTTPException(status_code=400, detail="Selecione um repositório autorizado antes de continuar.")
    return repo


class SelectRepository(BaseModel):
    repository: str = Field(min_length=3, max_length=200)


class PrepareChanges(BaseModel):
    branch_name: str = Field(min_length=1, max_length=80)
    commit_message: str = Field(min_length=3, max_length=200)
    files: list[dict[str, str]] = Field(min_length=1, max_length=20)


@router.get("/connect")
async def connect_github(request: Request):
    _, slug, _, public_url = _config()
    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state
    request.session.pop("github_installation_id", None)
    request.session.pop("github_selected_repo", None)
    install_url = f"https://github.com/apps/{slug}/installations/new?state={state}"
    if not public_url.startswith("https://") and not public_url.startswith("http://localhost"):
        raise HTTPException(status_code=503, detail="PUBLIC_APP_URL deve ser uma URL HTTPS pública.")
    return RedirectResponse(install_url, status_code=302)


@router.get("/callback")
async def github_setup_callback(request: Request, installation_id: int = Query(gt=0), setup_action: str = "install", state: str = ""):
    expected = request.session.pop("github_oauth_state", None)
    if not expected or not state or not secrets.compare_digest(str(expected), state):
        raise HTTPException(status_code=400, detail="Estado de autorização inválido ou expirado. Inicie a conexão novamente.")
    if setup_action not in {"install", "update"}:
        raise HTTPException(status_code=400, detail="Instalação do GitHub não concluída.")
    # Verifica a instalação na API autenticada como o próprio GitHub App;
    # não confia apenas no installation_id recebido na URL.
    installation = await _github_request("GET", f"/app/installations/{installation_id}", token=_app_jwt())
    account = installation.get("account") or {}
    if not account.get("login"):
        raise HTTPException(status_code=403, detail="Não foi possível validar a instalação do GitHub.")
    request.session["github_installation_id"] = installation_id
    request.session["github_account"] = str(account["login"])[:100]
    request.session.pop("github_selected_repo", None)
    _, _, _, public_url = _config()
    return RedirectResponse(public_url + "/?github=connected", status_code=303)


@router.get("/status")
async def github_status(request: Request) -> dict[str, Any]:
    return {
        "configured": all(os.getenv(k, "").strip() for k in ("GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_APP_PRIVATE_KEY", "GITHUB_SESSION_SECRET", "PUBLIC_APP_URL")),
        "connected": isinstance(request.session.get("github_installation_id"), int),
        "account": request.session.get("github_account"),
        "selected_repository": request.session.get("github_selected_repo"),
    }


@router.get("/repositories")
async def github_repositories(request: Request) -> dict[str, Any]:
    installation_id = _installation_id(request)
    token = await _installation_token(installation_id)
    data = await _github_request("GET", "/installation/repositories", token=token, params={"per_page": 100})
    repositories = []
    for item in data.get("repositories", []):
        if not isinstance(item, dict):
            continue
        repositories.append({
            "full_name": str(item.get("full_name", "")),
            "default_branch": str(item.get("default_branch", "main")),
            "private": bool(item.get("private", False)),
            "html_url": str(item.get("html_url", "")),
        })
    return {"repositories": repositories}


@router.post("/select-repository")
async def select_repository(body: SelectRepository, request: Request) -> dict[str, str]:
    installation_id = _installation_id(request)
    repo = body.repository.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise HTTPException(status_code=400, detail="Nome de repositório inválido.")
    # Confirma que o repositório pertence à instalação. Nenhum nome fornecido
    # pelo navegador é considerado autorizado sem verificação no GitHub.
    token = await _installation_token(installation_id, repository=repo)
    await _github_request("GET", f"/repos/{repo}", token=token)
    request.session["github_selected_repo"] = repo
    return {"selected_repository": repo}


@router.get("/file")
async def read_repository_file(request: Request, path: str = Query(min_length=1, max_length=500)):
    installation_id = _installation_id(request)
    repo = _selected_repo(request)
    clean_path = path.strip().lstrip("/")
    if not clean_path or ".." in clean_path.split("/") or clean_path.startswith(".git/"):
        raise HTTPException(status_code=400, detail="Caminho de arquivo inválido.")
    token = await _installation_token(installation_id, repository=repo, write=False)
    data = await _github_request("GET", f"/repos/{repo}/contents/{clean_path}", token=token)
    if data.get("type") != "file":
        raise HTTPException(status_code=400, detail="O caminho selecionado não é um arquivo.")
    try:
        raw = base64.b64decode(data.get("content", "").replace("\n", ""))
        content = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=415, detail="Este arquivo não é texto UTF-8 legível.")
    if len(content) > 250_000:
        raise HTTPException(status_code=413, detail="Arquivo muito grande para editar no chat (limite de 250 KB).")
    return {"repository": repo, "path": clean_path, "content": content, "sha": data.get("sha"), "html_url": data.get("html_url")}


@router.post("/prepare")
async def prepare_repository_changes(body: PrepareChanges, request: Request) -> dict[str, Any]:
    installation_id = _installation_id(request)
    repo = _selected_repo(request)
    branch = body.branch_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,78}[A-Za-z0-9]", branch) or ".." in branch.split("/") or branch in {"main", "master", "develop"}:
        raise HTTPException(status_code=400, detail="Use um nome de branch separado, como matheus-ai/correcao-login.")
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in body.files:
        path = str(item.get("path", "")).strip().lstrip("/")
        content = item.get("content")
        if not path or not isinstance(content, str) or len(content) > 500_000:
            raise HTTPException(status_code=400, detail="Cada arquivo precisa de caminho e conteúdo de texto com até 500 KB.")
        if ".." in path.split("/") or path.startswith(".git/") or path in seen:
            raise HTTPException(status_code=400, detail="Caminho inválido ou repetido na lista de alterações.")
        seen.add(path)
        files.append({"path": path, "content": content})
    token = await _installation_token(installation_id, repository=repo, write=True)
    repo_info = await _github_request("GET", f"/repos/{repo}", token=token)
    default_branch = str(repo_info.get("default_branch") or "main")
    ref = await _github_request("GET", f"/repos/{repo}/git/ref/heads/{default_branch}", token=token)
    base_sha = str((ref.get("object") or {}).get("sha") or "")
    if not base_sha:
        raise HTTPException(status_code=502, detail="Não foi possível localizar o commit-base do repositório.")
    await _github_request("POST", f"/repos/{repo}/git/refs", token=token, json_body={"ref": f"refs/heads/{branch}", "sha": base_sha})
    committed: list[str] = []
    for item in files:
        encoded = base64.b64encode(item["content"].encode("utf-8")).decode("ascii")
        existing_sha = None
        try:
            existing = await _github_request("GET", f"/repos/{repo}/contents/{item['path']}", token=token, params={"ref": branch})
            existing_sha = existing.get("sha")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        payload: dict[str, Any] = {
            "message": body.commit_message.strip()[:200],
            "content": encoded,
            "branch": branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha
        await _github_request("PUT", f"/repos/{repo}/contents/{item['path']}", token=token, json_body=payload)
        committed.append(item["path"])
    return {
        "repository": repo,
        "branch": branch,
        "files": committed,
        "url": f"https://github.com/{repo}/tree/{branch}",
        "message": "Alterações gravadas somente na nova branch. A branch principal não foi modificada.",
    }


@router.post("/disconnect")
async def disconnect_github(request: Request) -> dict[str, bool]:
    request.session.pop("github_installation_id", None)
    request.session.pop("github_account", None)
    request.session.pop("github_selected_repo", None)
    request.session.pop("github_oauth_state", None)
    return {"disconnected": True}
