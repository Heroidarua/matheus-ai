"""Transcrição de fala local com faster-whisper (pt-BR).

O navegador grava o turno de voz do usuário (WebM/Opus via MediaRecorder) e
envia para POST /api/stt. O modelo roda em CPU no próprio serviço; a primeira
chamada baixa os pesos do Hugging Face (cache em STT_CACHE_DIR).
"""
from __future__ import annotations

import io
import os
import threading
import wave

_MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "small").strip() or "small"
_CACHE_DIR = os.getenv("STT_CACHE_DIR", "").strip() or None
_MAX_AUDIO_SECONDS = 60

_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(data: bytes) -> str:
    """Transcreve WebM/Opus (MediaRecorder) ou WAV; devolve o texto em pt-BR."""
    model = _get_model()
    audio = _to_wav_bytes(data)
    segments, info = model.transcribe(
        io.BytesIO(audio),
        language="pt",
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return text[:2000]


def _to_wav_bytes(data: bytes) -> bytes:
    """Converte o áudio recebido para PCM 16 kHz mono (formato do Whisper).

    Aceita WAV diretamente; para WebM/Opus usa ffmpeg quando disponível.
    """
    if data[:4] == b"RIFF":
        return _resample_wav(data)
    # Tenta ffmpeg (presente na imagem Docker quando instalado)
    import shutil
    import subprocess
    if shutil.which("ffmpeg"):
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
            input=data, capture_output=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    raise ValueError("Áudio não reconhecido. Envie WebM/Opus gravado pelo navegador ou WAV.")


def _resample_wav(data: bytes) -> bytes:
    """Reamostra um WAV para 16 kHz mono 16-bit sem dependências externas."""
    import array
    src = io.BytesIO(data)
    with wave.open(src, "rb") as reader:
        frames = reader.readframes(reader.getnframes())
        width = reader.sampwidth
        channels = reader.getnchannels()
        rate = reader.getframerate()
    if width != 2:
        raise ValueError("WAV deve ser 16-bit.")
    samples = array.array("h")
    samples.frombytes(frames)
    if channels > 1:
        samples = samples[::channels]
    if rate != 16000:
        step = rate / 16000
        out_len = int(len(samples) / step)
        resampled = array.array("h", (samples[int(i * step)] for i in range(out_len)))
        samples = resampled
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(samples.tobytes())
    return out.getvalue()
