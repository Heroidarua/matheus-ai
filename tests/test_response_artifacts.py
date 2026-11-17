from __future__ import annotations

import uuid

from app import response_artifacts


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
                if normalized.startswith("INSERT INTO ADA_M_RESPONSE_ARTIFACTS"):
                    artifact_id, owner_id, file_name, content, char_count = params
                    database.rows[artifact_id] = (owner_id, file_name, content, char_count)
                elif normalized.startswith("SELECT FILE_NAME, CONTENT"):
                    artifact_id, owner_id = params
                    stored = database.rows.get(artifact_id)
                    self.row = (stored[1], stored[2]) if stored and stored[0] == owner_id else None
                elif normalized.startswith("DELETE FROM ADA_M_RESPONSE_ARTIFACTS"):
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


def test_short_response_is_not_saved_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert response_artifacts.save_response_artifact("session-1", "short answer") is None


def test_long_report_is_saved_and_only_owner_can_read(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(response_artifacts.psycopg, "connect", database.connect)

    report = "# Relatório\n\n" + ("Conteúdo completo. " * 400)
    saved = response_artifacts.save_response_artifact("session-1", report)

    assert saved is not None
    assert saved["characters"] == len(report)
    artifact_id = saved["id"]
    uuid.UUID(artifact_id)

    assert response_artifacts.get_response_artifact("session-1", artifact_id) == (
        saved["file_name"],
        report,
    )
    assert response_artifacts.get_response_artifact("another-session", artifact_id) is None


def test_invalid_artifact_id_is_rejected_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert response_artifacts.get_response_artifact("session-1", "../secret") is None


def test_oversized_report_is_not_saved(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    assert response_artifacts.save_response_artifact(
        "session-1",
        "x" * (response_artifacts.MAX_ARTIFACT_CHARS + 1),
    ) is None
