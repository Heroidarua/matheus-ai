from __future__ import annotations

import asyncio
import json
import os
import threading
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from vosk import KaldiRecognizer, Model, SetLogLevel

router = APIRouter()
MODEL_PATH = Path(os.getenv(
    "VOSK_MODEL_PATH",
    "/opt/ada-m/models/vosk-model-small-pt-0.3",
))
_model: Model | None = None
_model_lock = threading.Lock()
SetLogLevel(-1)


def _load_model() -> Model:
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            if not MODEL_PATH.is_dir():
                raise FileNotFoundError(
                    "Modelo Vosk PT-BR não encontrado. Execute scripts/install-vosk-model.sh."
                )
            _model = Model(str(MODEL_PATH))
    return _model


@router.websocket("/api/live/ws")
async def live_voice_socket(websocket: WebSocket) -> None:
    # A conexão aceita somente páginas servidas pelo mesmo host da ADA-M.
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "").lower()
    origin_host = ""
    if origin:
        from urllib.parse import urlparse
        origin_host = urlparse(origin).netloc.lower()

    if not origin_host or not host or origin_host != host:
        await websocket.close(code=4403, reason="Origem não autorizada")
        return

    await websocket.accept()
    try:
        await websocket.send_json({"type": "status", "message": "Carregando reconhecimento de voz..."})
        model = await asyncio.to_thread(_load_model)
        recognizer = KaldiRecognizer(model, 16000)
        recognizer.SetWords(False)
        await websocket.send_json({"type": "ready", "message": "Reconhecimento PT-BR pronto."})

        while True:
            audio = await websocket.receive_bytes()
            if not audio or len(audio) > 65536:
                continue
            completed = await asyncio.to_thread(recognizer.AcceptWaveform, audio)
            if completed:
                result = json.loads(recognizer.Result() or "{}")
                transcript = str(result.get("text", "")).strip()
                if transcript:
                    await websocket.send_json({"type": "transcript", "text": transcript})
            else:
                partial = json.loads(recognizer.PartialResult() or "{}").get("partial", "")
                if partial:
                    await websocket.send_json({"type": "partial"})
    except WebSocketDisconnect:
        return
    except FileNotFoundError as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
        except Exception:
            pass
    except Exception as exc:
        print("ADA-M Live WebSocket error:", type(exc).__name__)
        try:
            await websocket.send_json({"type": "error", "message": "Falha no reconhecimento de voz da VPS."})
            await websocket.close(code=1011)
        except Exception:
            pass
