from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/live/ws",
                headers={"origin": "https://evil.example"},
            ):
                pass
        assert error.value.code == 4403
