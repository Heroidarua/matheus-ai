from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import live_voice
from app.main import app


def test_live_websocket_transcribes_complete_whisper_utterance(monkeypatch, tmp_path) -> None:
    cli = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-base-q5_1.bin"
    cli.write_text("test")
    model.write_bytes(b"test")
    monkeypatch.setattr(live_voice, "ASR_BACKEND", "whisper_cpp")
    monkeypatch.setattr(live_voice, "WHISPER_CLI", str(cli))
    monkeypatch.setattr(live_voice, "WHISPER_MODEL", model)
    monkeypatch.setattr(live_voice, "VAD_SILENCE_SECONDS", 0.0)
    monkeypatch.setattr(live_voice, "_transcribe_whisper", lambda chunks: "ola mundo")

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/live/ws",
            headers={"origin": "http://testserver"},
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"
            assert websocket.receive_json()["type"] == "ready"

            # Três blocos de voz (384 ms), seguidos por silêncio.
            # O limite é zerado neste teste para não depender de tempo real.
            voiced = (b"\x88\x13" * 2048)
            silence = b"\x00\x00" * 2048
            for _ in range(3):
                websocket.send_bytes(voiced)
            for _ in range(9):
                websocket.send_bytes(silence)

            messages = [websocket.receive_json() for _ in range(3)]
            assert messages[0]["type"] == "status"
            assert messages[1] == {"type": "utterance", "text": "ola mundo"}
            assert messages[2]["type"] == "listening"


def test_live_websocket_keeps_vosk_as_optional_fallback(monkeypatch) -> None:
    class FakeRecognizer:
        def AcceptWaveform(self, audio: bytes) -> bool:
            return True

        def Result(self) -> str:
            return '{"text":"ola mundo"}'

    monkeypatch.setattr(live_voice, "ASR_BACKEND", "vosk")
    monkeypatch.setattr(live_voice, "_load_vosk_recognizer", lambda: FakeRecognizer())

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/live/ws",
            headers={"origin": "http://testserver"},
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_bytes(b"\x00\x00" * 1600)
            assert websocket.receive_json() == {"type": "transcript", "text": "ola mundo"}


def test_live_websocket_rejects_cross_origin() -> None:
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/live/ws",
                headers={"origin": "https://evil.example"},
            ):
                pass
        assert error.value.code == 4403
