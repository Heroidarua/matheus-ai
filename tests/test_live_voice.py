from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import live_voice
from app.main import app


class FakeRecognizer:
    def SetWords(self, enabled: bool) -> None:
        pass

    def AcceptWaveform(self, audio: bytes) -> bool:
        return True

    def Result(self) -> str:
        return json.dumps({"text": "ola mundo"})


def test_live_websocket_returns_vosk_transcript(monkeypatch) -> None:
    monkeypatch.setattr(live_voice, "_load_model", lambda: object())
    monkeypatch.setattr(live_voice, "KaldiRecognizer", lambda model, rate: FakeRecognizer())

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/live/ws",
            headers={"origin": "http://testserver"},
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_bytes(b"\x00\x00" * 1600)
            message = websocket.receive_json()
            assert message == {"type": "transcript", "text": "ola mundo"}


def test_live_websocket_rejects_cross_origin() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect(
                "/api/live/ws",
                headers={"origin": "https://evil.example"},
            ):
                assert False, "cross-origin WebSocket should be rejected"
        except Exception:
            pass
