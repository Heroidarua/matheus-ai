"""Persistent checkpoints and bounded history for ADA-M agent tasks."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg

_VOLATILE: dict[str, list[dict[str, Any]]] = {}
_SECRET_PATTERNS = (
    (re.compile(r"(?i)(authorization\\s*[:=]\\s*bearer\\s+)[^\\s\"']+"), r"\\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|password|passwd|secret)\\s*[:=]\\s*)[^\\s\"']+"), r"\\1[REDACTED]"),
    (re.compile(r"\\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\\b"), "[REDACTED]"),
)
_MAX_STATE_BYTES = 450_000


def _db():
    import os
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        return psycopg.connect(url, connect_timeout=4)
    except Exception as exc:
        print(f"Agent job database unavailable ({type(exc).__name__}); using process memory")
        return None


def _ensure(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ada_m_agent_jobs (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            state JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS ada_m_agent_jobs_owner_updated_idx
        ON ada_m_agent_jobs(owner_id, updated_at DESC)
    """)


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        result = value
        for pattern, replacement in _SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result[-16000:]
    if isinstance(value, list):
        return [_sanitize(item) for item in value[-80:]]
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize(str(value))


def _clean_state(state: dict[str, Any]) -> dict[str, Any]:
    clean = _sanitize(state if isinstance(state, dict) else {})
    encoded = json.dumps(clean, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > _MAX_STATE_BYTES:
        messages = clean.get("messages")
        if isinstance(messages, list):
            clean["messages"] = messages[-24:]
        events = clean.get("events")
        if isinstance(events, list):
            clean["events"] = events[-40:]
        clean["checkpoint_note"] = "Histórico reduzido para respeitar o limite de armazenamento."
        encoded = json.dumps(clean, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > _MAX_STATE_BYTES:
        raise ValueError("O checkpoint excede o limite seguro de armazenamento.")
    return clean


def create_job(owner_id: str, task: str, state: dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex
    save_job(owner_id, job_id, task, "running", state, create=True)
    return job_id


def save_job(
    owner_id: str,
    job_id: str,
    task: str,
    status: str,
    state: dict[str, Any],
    *,
    create: bool = False,
) -> None:
    if status not in {"running", "paused", "completed", "budget_exhausted", "failed"}:
        raise ValueError("Status de tarefa inválido.")
    clean = _clean_state(state)
    volatile_item = {
        "id": job_id, "owner_id": owner_id, "task": _sanitize(task),
        "status": status, "state": clean,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    conn = _db()
    if conn is None:
        items = _VOLATILE.setdefault(owner_id, [])
        existing = next((item for item in items if item["id"] == job_id), None)
        if existing:
            existing.update(volatile_item)
        else:
            items.append(volatile_item)
        del items[:-30]
        return
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                if create:
                    cur.execute(
                        """INSERT INTO ada_m_agent_jobs(id,owner_id,task,status,state)
                           VALUES(%s,%s,%s,%s,%s::jsonb)""",
                        (job_id, owner_id, _sanitize(task), status,
                         json.dumps(clean, ensure_ascii=False)),
                    )
                else:
                    cur.execute(
                        """UPDATE ada_m_agent_jobs SET task=%s,status=%s,state=%s::jsonb,
                           updated_at=NOW() WHERE id=%s AND owner_id=%s""",
                        (_sanitize(task), status, json.dumps(clean, ensure_ascii=False),
                         job_id, owner_id),
                    )
                    if cur.rowcount == 0:
                        cur.execute(
                            """INSERT INTO ada_m_agent_jobs(id,owner_id,task,status,state)
                               VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(id) DO NOTHING""",
                            (job_id, owner_id, _sanitize(task), status,
                             json.dumps(clean, ensure_ascii=False)),
                        )
    except Exception as exc:
        print(f"Agent job persistence unavailable ({type(exc).__name__}); using process memory")
        items = _VOLATILE.setdefault(owner_id, [])
        existing = next((item for item in items if item["id"] == job_id), None)
        if existing:
            existing.update(volatile_item)
        else:
            items.append(volatile_item)
        del items[:-30]
    finally:
        conn.close()


def get_pending_job(owner_id: str) -> dict[str, Any] | None:
    conn = _db()
    if conn is None:
        items = _VOLATILE.get(owner_id, [])
        return next((dict(item) for item in reversed(items)
                     if item.get("status") in {"paused", "running"}), None)
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute(
                    """SELECT id,task,status,state,created_at,updated_at
                       FROM ada_m_agent_jobs WHERE owner_id=%s
                       AND status IN ('paused','running')
                       ORDER BY updated_at DESC LIMIT 1""",
                    (owner_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        state = row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}")
        return {"id": row[0], "task": row[1], "status": row[2], "state": state,
                "created_at": row[4].isoformat(), "updated_at": row[5].isoformat()}
    except Exception as exc:
        print(f"Agent job lookup unavailable ({type(exc).__name__})")
        return None
    finally:
        conn.close()


def list_jobs(owner_id: str, limit: int = 10) -> list[dict[str, Any]]:
    limit = min(max(int(limit), 1), 20)
    conn = _db()
    if conn is None:
        items = list(reversed(_VOLATILE.get(owner_id, [])))[:limit]
        return [{"id": x["id"], "task": x["task"], "status": x["status"],
                 "updated_at": x["updated_at"], "state": x["state"]} for x in items]
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute(
                    """SELECT id,task,status,state,updated_at FROM ada_m_agent_jobs
                       WHERE owner_id=%s ORDER BY updated_at DESC LIMIT %s""",
                    (owner_id, limit),
                )
                rows = cur.fetchall()
        return [{"id": row[0], "task": row[1], "status": row[2],
                 "state": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                 "updated_at": row[4].isoformat()} for row in rows]
    except Exception as exc:
        print(f"Agent job history unavailable ({type(exc).__name__})")
        return []
    finally:
        conn.close()


def is_agent_continuation_request(message: str) -> bool:
    text = re.sub(r"\\s+", " ", str(message or "").casefold()).strip()
    return bool(re.fullmatch(
        r"(?:/continuar|continuar|continue|retomar|retome|retomar tarefa|"
        r"continue de onde parou|continuar de onde parou|retome a tarefa|"
        r"pode continuar|prossiga|siga em frente)(?: por favor)?[.! ]*",
        text,
    ))
