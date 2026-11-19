"""Arquivos criados pela ADA-M, privados por sessão e disponíveis para download."""
from __future__ import annotations

import json
import os
import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psycopg

MAX_FILE_CONTENT_CHARS = 200_000
MAX_GENERATED_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_SESSION = 30

MIME_TYPES = {
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".json": "application/json",
    ".html": "text/html; charset=utf-8",
    ".xml": "application/xml",
    ".py": "text/x-python; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".sql": "application/sql",
    ".log": "text/plain; charset=utf-8",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("Armazenamento de arquivos indisponível: configure DATABASE_URL no Render.")
    conn = psycopg.connect(url, connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ada_m_generated_files (
                id UUID PRIMARY KEY,
                owner_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content BYTEA NOT NULL,
                size_bytes BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ada_m_generated_files_owner_created "
            "ON ada_m_generated_files (owner_id, created_at DESC)"
        )
    conn.commit()
    return conn


def _build_file(file_name: str, content: str) -> tuple[bytes, str]:
    suffix = Path(file_name).suffix.lower()
    mime_type = MIME_TYPES.get(suffix)
    if not mime_type:
        raise ValueError("Formato não suportado. Use TXT, MD, CSV, JSON, HTML, XML, PY, JS, CSS, YAML, SQL, LOG, PDF, DOCX, XLSX ou PPTX.")

    if suffix in {".txt", ".md", ".csv", ".json", ".html", ".xml", ".py", ".js", ".css", ".yaml", ".yml", ".sql", ".log"}:
        if suffix == ".json":
            parsed = json.loads(content)
            content = json.dumps(parsed, ensure_ascii=False, indent=2)
        return content.encode("utf-8"), mime_type

    if suffix == ".pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from xml.sax.saxutils import escape

        output = BytesIO()
        document = SimpleDocTemplate(
            output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=Path(file_name).stem,
        )
        styles = getSampleStyleSheet()
        story = []
        for line in content.splitlines():
            clean = escape(line.strip())
            if not clean:
                story.append(Spacer(1, 5))
            elif line.startswith("# "):
                story.append(Paragraph(clean[2:] if clean.startswith("# ") else clean, styles["Title"]))
            elif line.startswith("## "):
                story.append(Paragraph(escape(line[3:].strip()), styles["Heading2"]))
            elif line.startswith("### "):
                story.append(Paragraph(escape(line[4:].strip()), styles["Heading3"]))
            else:
                story.append(Paragraph(clean, styles["BodyText"]))
        if not story:
            story.append(Paragraph("Documento ADA-M", styles["Title"]))
        document.build(story)
        return output.getvalue(), mime_type

    if suffix == ".docx":
        from docx import Document

        document = Document()
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("### "):
                document.add_heading(stripped[4:], level=3)
            elif stripped.startswith("## "):
                document.add_heading(stripped[3:], level=2)
            elif stripped.startswith("# "):
                document.add_heading(stripped[2:], level=1)
            else:
                document.add_paragraph(stripped)
        if not content.strip():
            document.add_paragraph("Documento ADA-M")
        output = BytesIO()
        document.save(output)
        return output.getvalue(), mime_type

    if suffix == ".xlsx":
        from openpyxl import Workbook

        payload = json.loads(content)
        sheets = payload.get("sheets") if isinstance(payload, dict) else None
        if not isinstance(sheets, list) or not sheets:
            rows = payload.get("rows") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ValueError("Para XLSX, content deve ser JSON com 'sheets' ou uma matriz 'rows'.")
            sheets = [{"name": "Dados", "rows": rows}]
        workbook = Workbook()
        default_sheet = workbook.active
        for index, sheet_data in enumerate(sheets[:20]):
            if not isinstance(sheet_data, dict) or not isinstance(sheet_data.get("rows"), list):
                raise ValueError("Cada planilha XLSX precisa conter 'name' e 'rows'.")
            sheet = default_sheet if index == 0 else workbook.create_sheet()
            sheet.title = re.sub(r"[\\/*?:\[\]]", "-", str(sheet_data.get("name") or f"Planilha {index + 1}"))[:31] or f"Planilha {index + 1}"
            for row in sheet_data["rows"][:10000]:
                if isinstance(row, list):
                    sheet.append([cell if isinstance(cell, (str, int, float, bool, type(None))) else json.dumps(cell, ensure_ascii=False) for cell in row[:100]])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue(), mime_type

    if suffix == ".pptx":
        from pptx import Presentation
        from pptx.util import Inches, Pt

        payload = json.loads(content)
        slides = payload.get("slides") if isinstance(payload, dict) else None
        if not isinstance(slides, list) or not slides:
            raise ValueError("Para PPTX, content deve ser JSON com uma lista 'slides'.")
        presentation = Presentation()
        for slide_data in slides[:60]:
            if not isinstance(slide_data, dict):
                continue
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = str(slide_data.get("title") or " ")
            body = slide.placeholders[1].text_frame
            body.clear()
            bullets = slide_data.get("bullets") or []
            if isinstance(bullets, str):
                bullets = [bullets]
            for index, item in enumerate(bullets[:30]):
                paragraph = body.paragraphs[0] if index == 0 else body.add_paragraph()
                paragraph.text = str(item)[:1000]
                paragraph.level = 0
                paragraph.font.size = Pt(20)
            if not bullets and slide_data.get("text"):
                body.text = str(slide_data["text"])[:5000]
        output = BytesIO()
        presentation.save(output)
        return output.getvalue(), mime_type

    raise ValueError("Formato não suportado.")


def create_generated_file(owner_id: str, name: str, content: str) -> dict[str, Any]:
    if not owner_id:
        raise ValueError("Não foi possível identificar a sessão atual.")
    if not isinstance(name, str) or not isinstance(content, str):
        raise ValueError("Nome e conteúdo do arquivo precisam ser textos.")
    if len(content) > MAX_FILE_CONTENT_CHARS:
        raise ValueError(f"O conteúdo ultrapassa o limite de {MAX_FILE_CONTENT_CHARS} caracteres.")
    file_name = Path(name.replace("\\", "/")).name.strip()
    file_name = re.sub(r"[\\x00-\\x1f\\x7f]", "", file_name)[:180]
    if not file_name or file_name in {".", ".."}:
        raise ValueError("Nome de arquivo inválido.")
    raw, mime_type = _build_file(file_name, content)
    if not raw or len(raw) > MAX_GENERATED_FILE_BYTES:
        raise ValueError("O arquivo ficou vazio ou ultrapassou o limite de 20 MB.")

    file_id = uuid.uuid4()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ada_m_generated_files
                    (id, owner_id, file_name, mime_type, content, size_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (file_id, owner_id, file_name, mime_type.split(";")[0], raw, len(raw)),
            )
            cur.execute(
                """
                DELETE FROM ada_m_generated_files
                WHERE owner_id = %s AND id NOT IN (
                    SELECT id FROM ada_m_generated_files
                    WHERE owner_id = %s ORDER BY created_at DESC LIMIT %s
                )
                """,
                (owner_id, owner_id, MAX_FILES_PER_SESSION),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": str(file_id),
        "file_name": file_name,
        "mime_type": mime_type.split(";")[0],
        "size_bytes": len(raw),
    }


def get_generated_file(owner_id: str, file_id: str) -> tuple[str, str, bytes] | None:
    if not owner_id:
        return None
    try:
        parsed_id = uuid.UUID(file_id)
    except (ValueError, TypeError, AttributeError):
        return None
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_name, mime_type, content
                FROM ada_m_generated_files
                WHERE id = %s AND owner_id = %s
                """,
                (parsed_id, owner_id),
            )
            row = cur.fetchone()
        return (str(row[0]), str(row[1]), bytes(row[2])) if row else None
    finally:
        conn.close()
