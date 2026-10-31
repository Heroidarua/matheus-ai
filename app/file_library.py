"""Biblioteca persistente de documentos para pesquisa da ADA-M.

Armazena texto extraído e metadados no PostgreSQL configurado por DATABASE_URL.
Arquivos nunca são executados; o conteúdo é sempre tratado como dado não confiável.
"""
from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from pypdf import PdfReader

def require_library_key(x_app_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("APP_API_KEY", "").strip()
    if expected and x_app_key != expected:
        raise HTTPException(status_code=401, detail="Chave da aplicação inválida.")


router = APIRouter(tags=["biblioteca de arquivos"], dependencies=[Depends(require_library_key)])
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 250_000
MAX_LIBRARY_DOCS = 500


class FileUpload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    mime_type: str = Field(default="application/octet-stream", max_length=120)
    data: str = Field(min_length=1)


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise HTTPException(
            status_code=503,
            detail="Banco de arquivos indisponível. Configure DATABASE_URL com um PostgreSQL persistente no Render.",
        )
    return value


def _connect():
    try:
        conn = psycopg.connect(_database_url(), connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ada_m_file_library (
                    id BIGSERIAL PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 CHAR(64) NOT NULL UNIQUE,
                    size_bytes BIGINT NOT NULL,
                    content_text TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        return conn
    except HTTPException:
        raise
    except Exception as exc:
        print(f"File library database error: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="Não foi possível acessar o banco de arquivos.")


def extract_text(name: str, mime_type: str, raw: bytes) -> str:
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".pdf" or mime_type == "application/pdf":
            reader = PdfReader(BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            from docx import Document
            doc = Document(BytesIO(raw))
            rows = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    rows.append(" | ".join(cell.text.replace("\n", " ") for cell in row.cells))
            text = "\n".join(rows)
        elif suffix in {".xlsx", ".xlsm"}:
            from openpyxl import load_workbook
            workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            rows = []
            for sheet in workbook.worksheets:
                rows.append(f"[Planilha: {sheet.title}]")
                for row in sheet.iter_rows(values_only=True):
                    values = [str(v) if v is not None else "" for v in row]
                    if any(values):
                        rows.append(" | ".join(values))
                    if sum(map(len, rows)) >= MAX_TEXT_CHARS:
                        break
                if sum(map(len, rows)) >= MAX_TEXT_CHARS:
                    break
            workbook.close()
            text = "\n".join(rows)
        else:
            text = raw.decode("utf-8-sig")
            if suffix == ".json":
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            elif suffix == ".csv":
                text = "\n".join(" | ".join(row) for row in csv.reader(text.splitlines()))
    except HTTPException:
        raise
    except Exception as exc:
        print(f"File extraction failed ({suffix}): {type(exc).__name__}")
        raise HTTPException(status_code=400, detail=f"Não foi possível extrair texto de {Path(name).name}.")
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="O arquivo não contém texto extraível. PDFs digitalizados precisam de OCR.")
    return text[:MAX_TEXT_CHARS]


@router.post("/api/files")
def upload_file(payload: FileUpload) -> dict[str, Any]:
    name = Path(payload.name.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    if not re.search(r"\.(pdf|docx|xlsx|xlsm|txt|md|csv|json)$", name, re.I):
        raise HTTPException(status_code=415, detail="Formatos aceitos: PDF, DOCX, XLSX, XLSM, TXT, MD, CSV e JSON.")
    try:
        raw = base64.b64decode(payload.data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Arquivo em base64 inválido.")
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Cada arquivo deve ter até 10 MB.")
    content = extract_text(name, payload.mime_type.lower(), raw)
    digest = hashlib.sha256(raw).hexdigest()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ada_m_file_library
                   (file_name, mime_type, sha256, size_bytes, content_text)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (sha256) DO NOTHING
                   RETURNING id""",
                (name, payload.mime_type[:120], digest, len(raw), content),
            )
            row = cur.fetchone()
            if row:
                file_id, duplicate = row[0], False
            else:
                cur.execute("SELECT id FROM ada_m_file_library WHERE sha256 = %s", (digest,))
                file_id, duplicate = cur.fetchone()[0], True
        conn.commit()
        return {"id": file_id, "name": name, "characters_indexed": len(content), "duplicate": duplicate}
    finally:
        conn.close()


@router.get("/api/files")
def list_files() -> dict[str, Any]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, file_name, mime_type, size_bytes, created_at,
                          char_length(content_text)
                   FROM ada_m_file_library ORDER BY created_at DESC LIMIT 200"""
            )
            rows = cur.fetchall()
        return {"files": [
            {"id": r[0], "name": r[1], "mime_type": r[2], "size_bytes": r[3],
             "created_at": r[4].isoformat(), "characters_indexed": r[5]}
            for r in rows
        ]}
    finally:
        conn.close()


def search_library(query: str, limit: int = 4) -> list[dict[str, Any]]:
    """Recuperação lexical de trechos de documentos persistidos."""
    terms = {
        t for t in re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)
        if len(t) >= 3 and t not in {"que", "para", "com", "uma", "dos", "das", "the", "and"}
    }
    if not terms:
        return []
    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, file_name, content_text FROM ada_m_file_library
                       ORDER BY created_at DESC LIMIT %s""",
                    (MAX_LIBRARY_DOCS,),
                )
                docs = cur.fetchall()
        finally:
            conn.close()
    except HTTPException:
        return []
    candidates = []
    for file_id, name, content in docs:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        for paragraph in paragraphs:
            pterms = set(re.findall(r"[^\W_]+", paragraph.casefold(), flags=re.UNICODE))
            overlap = terms & pterms
            if overlap:
                score = len(overlap) / max(1, len(pterms) ** 0.35)
                candidates.append((score, file_id, name, paragraph[:1800]))
    candidates.sort(key=lambda x: x[0], reverse=True)
    output, seen = [], set()
    for score, file_id, name, excerpt in candidates:
        key = (file_id, excerpt)
        if key in seen:
            continue
        seen.add(key)
        output.append({"id": file_id, "name": name, "excerpt": excerpt, "score": round(score, 4)})
        if len(output) >= max(1, min(limit, 8)):
            break
    return output


@router.get("/api/files/search")
def search_files(q: str = Query(min_length=2, max_length=500), limit: int = Query(default=8, ge=1, le=20)) -> dict[str, Any]:
    return {"query": q, "results": search_library(q, limit)}


@router.get("/api/files/status")
def file_library_status() -> dict[str, Any]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(size_bytes), 0), COALESCE(SUM(char_length(content_text)), 0) FROM ada_m_file_library")
            count, size, chars = cur.fetchone()
        return {"enabled": True, "documents": count, "original_bytes": size, "indexed_characters": chars, "storage": "PostgreSQL persistente"}
    finally:
        conn.close()


@router.delete("/api/files/{file_id}")
def delete_file(file_id: int) -> dict[str, Any]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ada_m_file_library WHERE id = %s RETURNING id", (file_id,))
            deleted = cur.fetchone()
        conn.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        return {"deleted": True, "id": file_id}
    finally:
        conn.close()
