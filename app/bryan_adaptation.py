"""Preferências adaptativas do Bryan, isoladas por sessão e persistidas no PostgreSQL."""
from __future__ import annotations

import os
import re
import threading
from typing import Any

import psycopg

_MODES = {"quiet", "balanced", "proactive"}
_VOLATILE: dict[str, str] = {}
_LOCK = threading.RLock()

_DIRECTIVES = (
    (re.compile(r"\b(bryan[,! ]+)?(fica quieto|fique quieto|fala menos|participe menos|não interrompa|nao interrompa|me deixe conversar)\b", re.I), "quiet"),
    (re.compile(r"\b(bryan[,! ]+)?(fala mais|participe mais|pode falar|pode participar|seja mais ativo|tenha mais iniciativa)\b", re.I), "proactive"),
    (re.compile(r"\b(bryan[,! ]+)?(equilibrado|do jeito normal|participação normal|participacao normal)\b", re.I), "balanced"),
)


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    return psycopg.connect(url, connect_timeout=4) if url else None


def _ensure(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS bryan_behavior_profile (
            owner_id TEXT PRIMARY KEY,
            participation_mode TEXT NOT NULL DEFAULT 'balanced'
                CHECK (participation_mode IN ('quiet', 'balanced', 'proactive')),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"""
    )


def get_profile(owner_id: str) -> dict[str, str]:
    conn = _connect()
    if conn is None:
        with _LOCK:
            return {"participation_mode": _VOLATILE.get(owner_id, "balanced")}
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute(
                    "SELECT participation_mode FROM bryan_behavior_profile WHERE owner_id=%s",
                    (owner_id,),
                )
                row = cur.fetchone()
        return {"participation_mode": row[0] if row else "balanced"}
    finally:
        conn.close()


def set_profile(owner_id: str, mode: str) -> dict[str, str]:
    if mode not in _MODES:
        raise ValueError("Modo de participação inválido.")
    conn = _connect()
    if conn is None:
        with _LOCK:
            _VOLATILE[owner_id] = mode
        return {"participation_mode": mode}
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute(
                    """INSERT INTO bryan_behavior_profile(owner_id, participation_mode)
                       VALUES (%s, %s)
                       ON CONFLICT(owner_id) DO UPDATE SET
                         participation_mode=EXCLUDED.participation_mode,
                         updated_at=NOW()""",
                    (owner_id, mode),
                )
        return {"participation_mode": mode}
    finally:
        conn.close()


def learn_preference(owner_id: str, message: str) -> dict[str, Any]:
    """Só altera o perfil quando o usuário expressa uma instrução clara."""
    text = re.sub(r"\s+", " ", str(message or "")).strip()[:1200]
    for pattern, mode in _DIRECTIVES:
        if pattern.search(text):
            profile = set_profile(owner_id, mode)
            return {"updated": True, **profile}
    return {"updated": False, **get_profile(owner_id)}


def delete_profile(owner_id: str) -> bool:
    conn = _connect()
    if conn is None:
        with _LOCK:
            return _VOLATILE.pop(owner_id, None) is not None
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute("DELETE FROM bryan_behavior_profile WHERE owner_id=%s", (owner_id,))
                return cur.rowcount > 0
    finally:
        conn.close()
