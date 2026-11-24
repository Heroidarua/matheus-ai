from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import time
import wave
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

ASR_BACKEND = os.getenv("ADA_LIVE_ASR", "whisper_cpp").strip().lower()
WHISPER_CLI = os.getenv("WHISPER_CLI_PATH", "/usr/local/bin/whisper-cli")
WHISPER_MODEL = Path(os.getenv(
    "WHISPER_MODEL_PATH",
    "/opt/ada-m/models/ggml-base-q5_1.bin",
))
VAD_RMS_THRESHOLD = float(os.getenv("ADA_LIVE_VAD_RMS", "0.0035"))
VAD_SILENCE_SECONDS = float(os.getenv("ADA_LIVE_VAD_SILENCE", "1.4"))
VAD_MAX_UTTERANCE_SECONDS = float(os.getenv("ADA_LIVE_MAX_UTTERANCE", "60"))
VAD_MIN_SPEECH_SECONDS = float(os.getenv("ADA_LIVE_MIN_SPEECH", "0.35"))
WHISPER_THREADS = max(1, int(os.getenv("ADA_LIVE_WHISPER_THREADS", "2")))
_whisper_semaphore = asyncio.Semaphore(1)


def _vad_threshold(noise_floor: float, *, speaking: bool = False) -> float:
    """Adaptive RMS gate with hysteresis, so quiet syllables are not dropped."""
    adaptive = max(VAD_RMS_THRESHOLD, noise_floor * 2.2)
    adaptive = min(adaptive, VAD_RMS_THRESHOLD * 2.2)
    return adaptive * (0.55 if speaking else 1.0)


def _transcribe_whisper(pcm_chunks: list[bytes]) -> str:
    if not Path(WHISPER_CLI).is_file():
        raise FileNotFoundError(
            "Whisper.cpp não está instalado. Execute scripts/install-whisper-cpp.sh."
        )
    if not WHISPER_MODEL.is_file():
        raise FileNotFoundError(
            "Modelo Whisper PT-BR não encontrado. Execute scripts/install-whisper-cpp.sh."
        )

    pcm = b"".join(pcm_chunks)
    if not pcm:
        return ""

    with tempfile.TemporaryDirectory(prefix="ada-live-") as temp_dir:
        wav_path = Path(temp_dir) / "utterance.wav"
        with wave.open(str(wav_path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(16000)
            audio_file.writeframes(pcm)

        command = [
            WHISPER_CLI,
            "-m", str(WHISPER_MODEL),
            "-f", str(wav_path),
            "-l", "pt",
            "-t", str(WHISPER_THREADS),
            "-nt",
            "-np",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-500:]
            raise RuntimeError(f"Whisper.cpp encerrou com erro: {detail}")
        lines = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip() != "[BLANK_AUDIO]"
        ]
        return " ".join(lines).strip()


def _load_vosk_recognizer():
    # Importação tardia: o modo Whisper não depende de carregar o Vosk.
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    model_path = Path(os.getenv(
        "VOSK_MODEL_PATH",
        "/opt/ada-m/models/vosk-model-small-pt-0.3",
    ))
    if not model_path.is_dir():
        raise FileNotFoundError(
            "Modelo Vosk PT-BR não encontrado. Execute scripts/install-vosk-model.sh."
        )
    recognizer = KaldiRecognizer(Model(str(model_path)), 16000)
    recognizer.SetWords(False)
    return recognizer


async def _send_transcription(websocket: WebSocket, chunks: list[bytes]) -> None:
    if not chunks:
        return
    async with _whisper_semaphore:
        transcript = await asyncio.to_thread(_transcribe_whisper, chunks)
    if transcript:
        await websocket.send_json({"type": "utterance", "text": transcript})


@router.websocket("/api/live/ws")
async def live_voice_socket(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "").lower()
    origin_host = urlparse(origin).netloc.lower() if origin else ""
    if not origin_host or not host or origin_host != host:
        await websocket.close(code=4403, reason="Origem não autorizada")
        return

    await websocket.accept()
    try:
        if ASR_BACKEND not in {"whisper_cpp", "vosk"}:
            raise RuntimeError("ADA_LIVE_ASR deve ser whisper_cpp ou vosk.")

        await websocket.send_json({"type": "status", "message": "Preparando reconhecimento de voz PT-BR..."})
        if ASR_BACKEND == "whisper_cpp":
            if not Path(WHISPER_CLI).is_file() or not WHISPER_MODEL.is_file():
                raise FileNotFoundError(
                    "Whisper.cpp ou o modelo Base quantizado não foi instalado. Execute scripts/install-whisper-cpp.sh."
                )
            await websocket.send_json({
                "type": "ready",
                "message": "Whisper.cpp PT-BR pronto. Fale normalmente; vou aguardar você concluir a frase.",
            })
            # Cerca de 450 ms de áudio anterior ao gatilho preservam o começo das palavras.
            pre_roll: deque[bytes] = deque(maxlen=5)
            utterance: list[bytes] = []
            speaking = False
            speech_started_at = 0.0
            last_voice_at = 0.0
            voiced_bytes = 0
            noise_floor = min(VAD_RMS_THRESHOLD * 0.5, 0.0015)

            while True:
                audio = await websocket.receive_bytes()
                if not audio or len(audio) > 65536 or len(audio) % 2:
                    continue
                samples = np.frombuffer(audio, dtype="<i2")
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) / 32768.0
                now = time.monotonic()

                # O limiar acompanha o ruído ambiente lentamente. Durante a fala,
                # a histerese reduz o limiar para não perder sílabas mais baixas.
                threshold = _vad_threshold(noise_floor, speaking=speaking)
                is_voice = rms >= threshold
                if not speaking and not is_voice:
                    noise_floor = (noise_floor * 0.92) + (rms * 0.08)

                if is_voice:
                    if not speaking:
                        speaking = True
                        speech_started_at = now
                        utterance = list(pre_roll)
                        voiced_bytes = 0
                    utterance.append(audio)
                    voiced_bytes += len(audio)
                    last_voice_at = now
                elif speaking:
                    # Mantém o áudio de cauda para o Whisper receber a frase inteira.
                    utterance.append(audio)

                if not speaking:
                    pre_roll.append(audio)
                    continue

                elapsed = now - speech_started_at
                silence_elapsed = now - last_voice_at
                should_finish = (
                    silence_elapsed >= VAD_SILENCE_SECONDS
                    or elapsed >= VAD_MAX_UTTERANCE_SECONDS
                )
                if should_finish:
                    completed = utterance
                    valid_speech = voiced_bytes / (16000 * 2) >= VAD_MIN_SPEECH_SECONDS
                    utterance = []
                    speaking = False
                    pre_roll.clear()
                    if valid_speech:
                        await websocket.send_json({"type": "status", "message": "Frase capturada. Convertendo sua fala em texto..."})
                        await _send_transcription(websocket, completed)
                        await websocket.send_json({"type": "listening", "message": "Pode falar novamente."})
        else:
            recognizer = await asyncio.to_thread(_load_vosk_recognizer)
            await websocket.send_json({"type": "ready", "message": "Vosk PT-BR pronto (modo alternativo)."})
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
    except WebSocketDisconnect:
        return
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)[:500]})
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
