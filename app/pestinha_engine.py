"""Sessões web do motor neural LIF original do Pestinha.

O navegador envia somente categorias de interação; nenhum texto de chat,
tecla digitada, URL ou conteúdo privado é coletado.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = ROOT / "vendor" / "pestinha"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))

from pestinha.core.nervous_system import LIFBrain
from pestinha.core.emotion import EmotionState
from pestinha.config import PROFILES

_EVENTS: dict[str, dict[str, float]] = {
    "pet": {"POKE": 0.9, "CARESS": 0.8},
    "typing": {"TYPING": 0.7, "WORK": 0.25},
    "submit": {"SOCIAL": 0.45, "WORK": 0.65, "NOVELTY": 0.25},
    "response": {"SOCIAL": 0.35, "NOVELTY": 0.15},
    "activity": {"MOTION": 0.2, "WEB": 0.15},
    "idle": {"SILENCE": 0.5},
}
_PROFILE = PROFILES["normal"]
_SESSIONS: dict[str, "PetNeuralSession"] = {}
_LOCK = threading.RLock()
_MAX_SESSIONS = 2000
_STEP_MS = 80


def _pet_config(pet_id: str) -> dict[str, Any]:
    path = VENDOR_ROOT / "pets" / f"{pet_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


class PetNeuralSession:
    def __init__(self, pet_id: str):
        config = _pet_config(pet_id)
        self.pet_id = pet_id
        self.brain = LIFBrain(
            seed=config.get("seed", 7),
            temperament=config.get("temperamento", {}),
        )
        self.emotion = EmotionState()
        self.last_event_at = 0.0
        self.last_seen = time.time()
        self.lock = threading.RLock()

    def stimulate(self, event: str) -> dict[str, Any]:
        if event not in _EVENTS:
            raise ValueError("Evento neural inválido.")
        with self.lock:
            now = time.time()
            self.last_seen = now
            # Evita que eventos repetidos acelerem artificialmente a simulação.
            if now - self.last_event_at < 0.08:
                return self.state()
            self.last_event_at = now
            self.brain.stimulate(_EVENTS[event])
            self.brain.step(_STEP_MS)
            if event == "pet":
                self.brain.learn(1.0, _STEP_MS / 1000.0, _PROFILE["learn_rate"])
            motors = self.brain.motor_activity()
            emotion = self.emotion.update(motors, _STEP_MS / 1000.0, _PROFILE)
            return self.state(emotion, motors)

    def state(self, emotion: str | None = None, motors: dict[str, float] | None = None) -> dict[str, Any]:
        motors = motors if motors is not None else self.brain.motor_activity()
        return {
            "pet": self.pet_id,
            "emotion": emotion or self.emotion.current,
            "valence": round(float(self.emotion.valence), 3),
            "arousal": round(float(self.emotion.arousal), 3),
            "neurons": int(self.brain.N),
            "synapses": int(self.brain.n_synapses),
            "motor": max(motors, key=motors.get) if motors else "WATCH",
            "learning": bool(self.brain.learned.any()),
            "engine": "original-pestinha-lif",
            "note": "Emoção computacional produzida pela rede LIF; não representa sentimento subjetivo.",
        }


def stimulate_session(session_id: str, pet_id: str, event: str) -> dict[str, Any]:
    if pet_id not in {"bryan", "jorge"}:
        pet_id = "bryan"
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None or session.pet_id != pet_id:
            if len(_SESSIONS) >= _MAX_SESSIONS:
                oldest = min(_SESSIONS, key=lambda key: _SESSIONS[key].last_seen)
                _SESSIONS.pop(oldest, None)
            session = PetNeuralSession(pet_id)
            _SESSIONS[session_id] = session
    return session.stimulate(event)
