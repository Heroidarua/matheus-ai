from __future__ import annotations

import asyncio
import hmac
import io
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import soundfile as sf
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

ENGINE_ROOT = Path(os.getenv("TINY_VOCA_PATH", "/opt/ada-m-tts/engine"))
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from tiny_voca_ptbr import Voice  # noqa: E402
from tiny_voca_ptbr.text import NothingToPronounce  # noqa: E402

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ada-m-tts")
generation_lock = asyncio.Lock()


class SpeechRequest(BaseModel):
    model: str = "tiny-voca-ptbr"
    input: str = Field(min_length=1, max_length=3000)
    voice: str = "F"
    response_format: Literal["wav"] = "wav"
    speed: float = Field(default=1.0, ge=0.7, le=1.3)


def _voice_code(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"f", "female", "pf_dora", "pt-br-female"}:
        return "F"
    if normalized in {"m", "male", "pm_santa", "pt-br-male"}:
        return "M"
    raise HTTPException(status_code=422, detail="Voz inválida. Use F (feminina) ou M (masculina).")


def _render_wav(engine: Voice, text: str, voice: str, speed: float) -> bytes:
    waveform, _ = engine.speak(
        text,
        voice=voice,
        speed=speed,
        pitch_range=1.05,
    )
    buffer = io.BytesIO()
    sf.write(buffer, waveform, engine.sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Carregando tiny-voca pt-BR em CPU (1 thread)")
    app.state.voice = Voice(threads=1)
    logger.info("Modelo carregado: tiny-voca pt-BR, 24 kHz")
    yield


app = FastAPI(
    title="ADA-M Local TTS",
    version="1.0.0",
    description="Síntese de voz pt-BR local com tiny-voca ONNX.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, object]:
    ready = hasattr(app.state, "voice")
    return {
        "status": "ok" if ready else "starting",
        "engine": "tiny-voca-ptbr",
        "language": "pt-BR",
        "sample_rate": 24000,
        "ready": ready,
    }


@app.post("/v1/audio/speech")
async def create_speech(
    data: SpeechRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    expected = os.getenv("TTS_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="TTS_API_KEY não configurada no serviço de voz.")

    scheme, separator, supplied = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip(), expected):
        raise HTTPException(status_code=401, detail="Autenticação inválida.")

    engine: Voice | None = getattr(request.app.state, "voice", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Modelo de voz ainda está carregando.")

    selected_voice = _voice_code(data.voice)
    try:
        # Serializa as inferências para manter o uso de CPU e RAM previsível.
        async with generation_lock:
            audio = await run_in_threadpool(
                _render_wav, engine, data.input.strip(), selected_voice, data.speed
            )
    except NothingToPronounce as exc:
        raise HTTPException(status_code=422, detail="O texto não contém palavras em português para leitura.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha ao sintetizar áudio (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Não foi possível sintetizar o áudio.") from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "X-TTS-Engine": "tiny-voca-ptbr",
            "X-TTS-Voice": selected_voice,
        },
    )
