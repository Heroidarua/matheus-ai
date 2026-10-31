from __future__ import annotations

import base64

import pytest
from fastapi import HTTPException

from app.file_library import extract_text, search_library, upload_file, FileUpload


def test_extract_plain_text():
    text = extract_text("notas.txt", "text/plain", b"Pesquisa sobre Python e automacao")
    assert "Python" in text


def test_extract_csv_as_readable_rows():
    text = extract_text("dados.csv", "text/csv", b"nome,idade\nAna,27\n")
    assert "nome | idade" in text
    assert "Ana | 27" in text


def test_extract_json_pretty_prints():
    text = extract_text("dados.json", "application/json", b'{"ok":true,"count":2}')
    assert '"ok": true' in text


def test_empty_document_is_rejected():
    with pytest.raises(HTTPException) as error:
        extract_text("vazio.txt", "text/plain", b"   ")
    assert error.value.status_code == 422


def test_unknown_extension_is_rejected_without_database_access():
    payload = FileUpload(name="script.exe", data=base64.b64encode(b"not executable").decode())
    with pytest.raises(HTTPException) as error:
        upload_file(payload)
    assert error.value.status_code == 415


def test_search_gracefully_skips_when_database_is_not_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert search_library("consulta de documentos") == []
