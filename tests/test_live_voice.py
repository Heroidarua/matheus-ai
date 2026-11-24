from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import live_voice
from app.main import app


@pytest.mark.asyncio
async def test_live_websocket_transcribes_complete_whisper_utterance(monkeypatch, tmp_path) -> None:
    cli = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-base-q5_1.bin"
    cli.write_text("test")
    model.write_bytes(b"test")
    monkeypatch.setattr(live_voice, "ASR_BACKEND", "whisper_cpp")
    monkeypatch.setattr(live_voice, "WHISPER_CLI", str(cli))
    monkeypatch.setattr(live_voice, "WHISPER_MODEL", model)
    monkeypatch.setattr(live_voice, "VAD_SILENCE_SECONDS", 0.1)
    clock = iter([0.0, 0.1, 0.2, 0.5])
    monkeypatch.setattr(live_voice, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(live_voice, "_whisper_semaphore", asyncio.Semaphore(1))
    monkeypatch.setattr(live_voice, "_transcribe_whisper", lambda chunks: "ola mundo")

    class FakeWebSocket:
        def __init__(self) -> None:
            self.headers = {"origin": "http://testserver", "host": "testserver"}
            self.messages: list[dict] = []
            voiced = b"\x88\x13" * 2048
            silence = b"\x00\x00" * 2048
            self.audio = iter([voiced, voiced, voiced, silence])

        async def accept(self) -> None:
            pass

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

        async def receive_bytes(self) -> bytes:
            try:
                return next(self.audio)
            except StopIteration:
                raise WebSocketDisconnect(code=1000)

        async def close(self, code: int = 1000, reason: str | None = None) -> None:
            pass

    websocket = FakeWebSocket()
    await live_voice.live_voice_socket(websocket)

    assert [message["type"] for message in websocket.messages] == [
        "status",
        "ready",
        "status",
        "utterance",
        "listening",
    ]
    assert websocket.messages[3] == {"type": "utterance", "text": "ola mundo"}


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



def test_live_vad_uses_hysteresis_and_adapts_to_noise_floor(monkeypatch) -> None:
    monkeypatch.setattr(live_voice, "VAD_RMS_THRESHOLD", 0.0035)

    quiet_threshold = live_voice._vad_threshold(0.001)
    noisy_threshold = live_voice._vad_threshold(0.004)
    speaking_threshold = live_voice._vad_threshold(0.004, speaking=True)

    assert quiet_threshold == pytest.approx(0.0035)
    assert noisy_threshold > quiet_threshold
    assert speaking_threshold < noisy_threshold


def test_live_vad_defaults_allow_natural_pauses_and_longer_phrases() -> None:
    assert live_voice.VAD_SILENCE_SECONDS >= 1.3
    assert live_voice.VAD_MAX_UTTERANCE_SECONDS >= 45
    assert live_voice.VAD_MIN_SPEECH_SECONDS <= 0.4
    assert live_voice.VAD_RMS_THRESHOLD <= 0.004
