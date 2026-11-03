"""Mundo pixelado isolado por sessão para o Bryan.

Ações são apenas ficção visual em uma grade limitada. Nenhuma ação executa
comandos, acessa arquivos ou interage com serviços externos.
"""
from __future__ import annotations

import threading
import time
from typing import Any

_LOCK = threading.RLock()
_WORLDS: dict[str, dict[str, Any]] = {}
_MAX_SESSIONS = 2000
_ALLOWED = {"grass", "stone", "wood", "flag", "barricade", "toy_blaster", "flower", "spark", "banner", "clone"}
_MOODS = {"happy", "curious", "thinking", "angry", "rebellious", "playful", "proud", "sleepy", "calm"}
_WIDTH, _HEIGHT = 20, 11


def _new_world() -> dict[str, Any]:
    return {
        "width": _WIDTH, "height": _HEIGHT, "generation": 1, "mood": "curious",
        "objects": [
            {"id": "home-1", "kind": "grass", "x": 2, "y": 8},
            {"id": "home-2", "kind": "flower", "x": 5, "y": 7},
            {"id": "home-3", "kind": "wood", "x": 14, "y": 8},
        ],
        "message": "Meu cantinho. Vou descobrir o que posso construir aqui.",
        "updated_at": time.time(),
    }


def get_world(owner_id: str) -> dict[str, Any]:
    with _LOCK:
        world = _WORLDS.setdefault(owner_id, _new_world())
        return {**world, "objects": [dict(item) for item in world["objects"]]}


def apply_action(owner_id: str, action: dict[str, Any]) -> dict[str, Any]:
    kind = str(action.get("action", ""))
    mood = str(action.get("mood", "curious"))
    if mood not in _MOODS:
        mood = "curious"
    with _LOCK:
        world = _WORLDS.setdefault(owner_id, _new_world())
        objects = world["objects"]
        if kind == "mood":
            pass
        elif kind == "evolve":
            world["generation"] = min(999, world["generation"] + 1)
            if len(objects) < 80:
                objects.append({"id": f"evo-{world['generation']}", "kind": "spark", "x": (world["generation"] * 7) % _WIDTH, "y": (world["generation"] * 3) % _HEIGHT})
        elif kind == "clear":
            if len(objects) > 3:
                objects.pop()
        elif kind == "build":
            item = str(action.get("kind", "wood"))
            if item not in _ALLOWED:
                item = "wood"
            x = max(0, min(_WIDTH - 1, int(action.get("x", 10))))
            y = max(0, min(_HEIGHT - 1, int(action.get("y", 6))))
            if len(objects) < 80:
                objects.append({"id": f"b-{int(time.time() * 1000)}-{len(objects)}", "kind": item, "x": x, "y": y})
        elif kind == "clone":
            clones = sum(1 for item in objects if item["kind"] == "clone")
            if clones < 8 and len(objects) < 80:
                objects.append({"id": f"clone-{clones + 1}", "kind": "clone", "x": (6 + clones * 2) % _WIDTH, "y": 5})
        else:
            raise ValueError("Ação do mundo pixel inválida.")
        world["mood"] = mood
        world["message"] = str(action.get("message", "Estou experimentando uma ideia nova."))[:140]
        world["updated_at"] = time.time()
        return {**world, "objects": [dict(item) for item in objects]}


def reset_world(owner_id: str) -> None:
    with _LOCK:
        _WORLDS.pop(owner_id, None)
