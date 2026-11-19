from __future__ import annotations

import uuid

import pytest

from app import generated_files


class FakeDatabase:
    def __init__(self):
        self.rows = {}

    def connect(self, *args, **kwargs):
        database = self

        class Cursor:
            row = None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, query, params=()):
                normalized = " ".join(query.split()).upper()
                if normalized.startswith("INSERT INTO ADA_M_GENERATED_FILES"):
                    file_id, owner_id, name, mime_type, content, size = params
                    database.rows[file_id] = (owner_id, name, mime_type, bytes(content), size)
                elif normalized.startswith("SELECT FILE_NAME, MIME_TYPE, CONTENT"):
                    file_id, owner_id = params
                    stored = database.rows.get(file_id)
                    self.row = (stored[1], stored[2], stored[3]) if stored and stored[0] == owner_id else None
                elif normalized.startswith("DELETE FROM ADA_M_GENERATED_FILES"):
                    return None

            def fetchone(self):
                return self.row

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self):
                return None

            def close(self):
                return None

        return Connection()


def test_text_file_is_saved_and_download_is_session_private(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(generated_files.psycopg, "connect", database.connect)

    saved = generated_files.create_generated_file("session-1", "anotacoes.txt", "Olá, ADA-M!")
    assert saved["file_name"] == "anotacoes.txt"
    uuid.UUID(saved["id"])
    assert generated_files.get_generated_file("session-1", saved["id"]) == (
        "anotacoes.txt", "text/plain", "Olá, ADA-M!".encode("utf-8")
    )
    assert generated_files.get_generated_file("another-session", saved["id"]) is None


def test_unsupported_extension_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    with pytest.raises(ValueError, match="Formato não suportado"):
        generated_files.create_generated_file("session-1", "program.exe", "nope")


def test_invalid_id_is_rejected_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert generated_files.get_generated_file("session-1", "../private") is None


def test_pdf_and_office_formats_are_generated(monkeypatch):
    pytest.importorskip("reportlab")
    pytest.importorskip("docx")
    pytest.importorskip("openpyxl")
    pytest.importorskip("pptx")
    pdf, _ = generated_files._build_file("relatorio.pdf", "# Relatório\nConteúdo")
    docx, _ = generated_files._build_file("relatorio.docx", "# Relatório\nConteúdo")
    xlsx, _ = generated_files._build_file("dados.xlsx", '{"rows":[["Nome"],["ADA-M"]]}')
    pptx, _ = generated_files._build_file("apresentacao.pptx", '{"slides":[{"title":"ADA-M","bullets":["Primeiro slide"]}]}')
    assert pdf.startswith(b"%PDF")
    assert docx.startswith(b"PK")
    assert xlsx.startswith(b"PK")
    assert pptx.startswith(b"PK")
