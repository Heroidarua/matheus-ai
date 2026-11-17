"""Persistência de relatórios longos do chat em PostgreSQL.

Os artefatos são privados por sessão e só são disponibilizados após a geração
ser finalizada pelo servidor. Não substituem o histórico normal do chat.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg

MIN_ARTIFACT_CHARS = 5000


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _connect():
    url = _database_url()
    if not url:
        return None
    conn = psycopg.connect(url, connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ada_m_response_artifacts (
                id UUID PRIMARY KEY,
                owner_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ada_m_response_artifacts_owner_created "
            "ON ada_m_response_artifacts (owner_id, created_at DESC)"
        )
    conn.commit()
    return conn


def save_response_artifact(owner_id: str, content: str) -> dict[str, Any] | None:
    """Save only substantial completed responses; return safe download metadata."""
    text = content if isinstance(content, str) else ""
    if not owner_id or len(text) < MIN_ARTIFACT_CHARS:
        return None
    conn = _connect()
    if conn is None:
        return None
    artifact_id = uuid.uuid4()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_name = f"relatorio-ada-m-{stamp}.md"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ada_m_response_artifacts
                    (id, owner_id, file_name, content, char_count)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (artifact_id, owner_id, file_name, text, len(text)),
            )
            # Retém no máximo os 30 relatórios mais recentes por sessão.
            cur.execute(
                """
                DELETE FROM ada_m_response_artifacts
                WHERE owner_id = %s AND id NOT IN (
                    SELECT id FROM ada_m_response_artifacts
                    WHERE owner_id = %s
                    ORDER BY created_at DESC LIMIT 30
                )
                """,
                (owner_id, owner_id),
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": str(artifact_id), "file_name": file_name, "characters": len(text)}


def get_response_artifact(owner_id: str, artifact_id: str) -> tuple[str, str] | None:
    """Return a report only when it belongs to the current browser session."""
    if not owner_id:
        return None
    try:
        parsed_id = uuid.UUID(artifact_id)
    except (ValueError, TypeError, AttributeError):
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_name, content
                FROM ada_m_response_artifacts
                WHERE id = %s AND owner_id = %s
                """,
                (parsed_id, owner_id),
            )
            row = cur.fetchone()
        return (str(row[0]), str(row[1])) if row else None
    finally:
        conn.close()
