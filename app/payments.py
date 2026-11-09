from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/payments", tags=["payments"])

PRICE = Decimal("5.00")
ACCESS_HOURS = 24
MP_API = "https://api.mercadopago.com"


def _config() -> tuple[str, str, str]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
    webhook_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    return database_url, access_token, webhook_secret


def _connect():
    database_url, _, _ = _config()
    if not database_url:
        raise RuntimeError("DATABASE_URL não configurada")
    return psycopg.connect(database_url, connect_timeout=8)


def _ensure_schema() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ada_m_payments (
                    id BIGSERIAL PRIMARY KEY,
                    mp_payment_id TEXT UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    amount NUMERIC(10,2) NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    approved_at TIMESTAMPTZ
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS ada_m_payments_session_idx
                ON ada_m_payments (session_id, created_at DESC)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ada_m_subscriptions (
                    session_id TEXT PRIMARY KEY,
                    expires_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)


def _session_id(request: Request) -> str:
    session_id = request.session.get("companion_id")
    if not session_id:
        import secrets
        session_id = secrets.token_urlsafe(32)
        request.session["companion_id"] = session_id
    return str(session_id)


def _access_record(session_id: str) -> datetime | None:
    _ensure_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT expires_at FROM ada_m_subscriptions WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            return row[0] if row else None


def _activate_payment(payment_id: str, mp_data: dict[str, Any]) -> bool:
    external_reference = str(mp_data.get("external_reference") or "")
    if not external_reference:
        return False
    try:
        amount = Decimal(str(mp_data.get("transaction_amount", "0"))).quantize(Decimal("0.01"))
    except Exception:
        return False
    if (
        mp_data.get("status") != "approved"
        or amount != PRICE
        or mp_data.get("currency_id") != "BRL"
        or str(mp_data.get("id")) != str(payment_id)
    ):
        return False

    _ensure_schema()
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, session_id, status, approved_at FROM ada_m_payments WHERE mp_payment_id = %s FOR UPDATE",
                (str(payment_id),),
            )
            row = cur.fetchone()
            if not row or row[1] != external_reference:
                return False
            if row[3] is not None:
                cur.execute("UPDATE ada_m_payments SET status = 'approved' WHERE mp_payment_id = %s", (str(payment_id),))
                return True
            cur.execute(
                "SELECT expires_at FROM ada_m_subscriptions WHERE session_id = %s FOR UPDATE",
                (external_reference,),
            )
            current = cur.fetchone()
            start = current[0] if current and current[0] > now else now
            expiry = start + timedelta(hours=ACCESS_HOURS)
            cur.execute("""
                INSERT INTO ada_m_subscriptions (session_id, expires_at, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (session_id) DO UPDATE
                SET expires_at = EXCLUDED.expires_at, updated_at = NOW()
            """, (external_reference, expiry))
            cur.execute("""
                UPDATE ada_m_payments
                SET status = 'approved', approved_at = NOW()
                WHERE mp_payment_id = %s
            """, (str(payment_id),))
    return True


async def _fetch_mp_payment(payment_id: str, access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=6.0)) as client:
        response = await client.get(
            f"{MP_API}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível consultar o pagamento no Mercado Pago.")
    data = response.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Resposta inválida do Mercado Pago.")
    return data


async def require_paid_access(request: Request) -> None:
    """Bloqueia somente quando a integração está ativa e não há assinatura vigente."""
    database_url, access_token, _ = _config()
    if not database_url or not access_token:
        return
    try:
        expiry = await asyncio.to_thread(_access_record, _session_id(request))
    except Exception as exc:
        print(f"Payment access check failed ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="Não foi possível validar o acesso agora.")
    if not expiry or expiry <= datetime.now(timezone.utc):
        raise HTTPException(status_code=402, detail="subscription_required")


class PixCreateRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")


@router.get("/access")
async def access_status(request: Request) -> dict[str, Any]:
    database_url, access_token, _ = _config()
    enabled = bool(database_url and access_token)
    if not enabled:
        return {"payments_enabled": False, "active": True, "expires_at": None}
    try:
        expiry = await asyncio.to_thread(_access_record, _session_id(request))
    except Exception as exc:
        print(f"Payment database unavailable ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="O banco de dados de pagamentos está indisponível.")
    now = datetime.now(timezone.utc)
    return {
        "payments_enabled": True,
        "active": bool(expiry and expiry > now),
        "expires_at": expiry.isoformat() if expiry else None,
        "price": "5.00",
        "duration_hours": ACCESS_HOURS,
    }


@router.post("/pix")
async def create_pix(data: PixCreateRequest, request: Request) -> dict[str, Any]:
    database_url, access_token, _ = _config()
    if not database_url or not access_token:
        raise HTTPException(status_code=503, detail="A integração Pix ainda não está configurada.")
    session_id = _session_id(request)
    try:
        await asyncio.to_thread(_ensure_schema)
    except Exception as exc:
        print(f"Payment database unavailable ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="Não foi possível acessar o banco de pagamentos.")

    idempotency_key = str(uuid.uuid4())
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ada_m_payments (idempotency_key, session_id, amount, status)
                       VALUES (%s, %s, %s, 'creating')""",
                    (idempotency_key, session_id, PRICE),
                )
        public_url = (os.getenv("ADA_PUBLIC_URL") or os.getenv("PUBLIC_APP_URL", "")).strip().rstrip("/")
        if not public_url:
            public_url = str(request.base_url).rstrip("/")
        payload = {
            "transaction_amount": float(PRICE),
            "description": "ADA-M - acesso por 24 horas",
            "payment_method_id": "pix",
            "payer": {"email": str(data.email)},
            "external_reference": session_id,
            "notification_url": public_url + "/api/payments/webhook",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.post(
                f"{MP_API}/v1/payments",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                },
                json=payload,
            )
        if response.status_code >= 400:
            print(f"Mercado Pago create payment HTTP {response.status_code}")
            raise HTTPException(status_code=502, detail="O Mercado Pago não conseguiu gerar o Pix. Confira as credenciais e tente novamente.")
        mp_data = response.json()
        payment_id = str(mp_data.get("id") or "")
        transaction = ((mp_data.get("point_of_interaction") or {}).get("transaction_data") or {})
        qr_code = transaction.get("qr_code")
        if not payment_id or not qr_code:
            raise HTTPException(status_code=502, detail="O Mercado Pago não retornou os dados do Pix.")
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ada_m_payments SET mp_payment_id = %s, status = %s WHERE idempotency_key = %s",
                    (payment_id, str(mp_data.get("status") or "pending"), idempotency_key),
                )
        return {
            "payment_id": payment_id,
            "status": str(mp_data.get("status") or "pending"),
            "qr_code": qr_code,
            "qr_code_base64": transaction.get("qr_code_base64"),
            "ticket_url": transaction.get("ticket_url"),
            "expires_at": mp_data.get("date_of_expiration"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Pix creation failed ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível criar a cobrança Pix agora.")


@router.get("/status/{payment_id}")
async def payment_status(payment_id: str, request: Request) -> dict[str, Any]:
    database_url, access_token, _ = _config()
    if not database_url or not access_token:
        raise HTTPException(status_code=503, detail="A integração Pix ainda não está configurada.")
    session_id = _session_id(request)
    try:
        _ensure_schema()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM ada_m_payments WHERE mp_payment_id = %s AND session_id = %s",
                    (payment_id, session_id),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Pagamento não encontrado nesta sessão.")
        mp_data = await _fetch_mp_payment(payment_id, access_token)
        if str(mp_data.get("external_reference") or "") != session_id:
            raise HTTPException(status_code=403, detail="Pagamento não pertence a esta sessão.")
        status = str(mp_data.get("status") or "unknown")
        if status == "approved":
            await asyncio.to_thread(_activate_payment, payment_id, mp_data)
        else:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE ada_m_payments SET status = %s WHERE mp_payment_id = %s AND session_id = %s AND approved_at IS NULL",
                        (status, payment_id, session_id),
                    )
        expiry = await asyncio.to_thread(_access_record, session_id)
        active = bool(expiry and expiry > datetime.now(timezone.utc))
        return {"status": status, "active": active, "expires_at": expiry.isoformat() if expiry else None}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Payment status check failed ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível verificar o pagamento agora.")


def _valid_signature(secret: str, signature: str, request_id: str, resource_id: str) -> bool:
    parts = {}
    for item in signature.split(","):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            parts[key] = value
    ts, received = parts.get("ts"), parts.get("v1")
    if not ts or not received or not request_id or not resource_id:
        return False
    manifest = f"id:{resource_id.lower()};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.post("/webhook")
async def mercadopago_webhook(request: Request) -> dict[str, str]:
    _, access_token, webhook_secret = _config()
    if not access_token or not webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook ainda não configurado.")
    try:
        body = await request.json()
    except Exception:
        body = {}
    data = body.get("data") if isinstance(body, dict) else {}
    resource_id = str(request.query_params.get("data.id") or (data or {}).get("id") or "")
    event_type = str(request.query_params.get("type") or (body or {}).get("type") or "")
    if event_type not in {"payment", "payments"} or not resource_id:
        return {"received": "ignored"}
    if not _valid_signature(
        webhook_secret,
        request.headers.get("x-signature", ""),
        request.headers.get("x-request-id", ""),
        resource_id,
    ):
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida.")
    mp_data = await _fetch_mp_payment(resource_id, access_token)
    if mp_data.get("status") == "approved":
        await asyncio.to_thread(_activate_payment, resource_id, mp_data)
    else:
        _ensure_schema()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ada_m_payments SET status = %s WHERE mp_payment_id = %s AND approved_at IS NULL",
                    (str(mp_data.get("status") or "unknown"), resource_id),
                )
    return {"received": "ok"}
