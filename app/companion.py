"""Personalidade e estado afetivo simulado da ADA-M/Matheus AI.

O módulo não treina pesos nem afirma consciência: mantém um estado conversacional
leve, com decaimento gradual e persistência opcional no PostgreSQL já usado pelo app.
Nenhum texto bruto das conversas é armazenado aqui.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import psycopg

BASELINE: dict[str, float] = {
    "joy": 0.35,
    "calm": 0.68,
    "curiosity": 0.55,
    "empathy": 0.58,
    "confidence": 0.62,
    "frustration": 0.04,
    "surprise": 0.10,
}
_FIELDS = tuple(BASELINE)
_MEMORY_STATE: dict[str, dict[str, float]] = {}
_DECAY = 0.88


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _load_state(session_id: str) -> dict[str, float]:
    if not _database_url():
        return dict(_MEMORY_STATE.get(session_id, BASELINE))
    try:
        with psycopg.connect(_database_url(), connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ada_m_companion_state (
                        session_id TEXT PRIMARY KEY,
                        state_json JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "SELECT state_json FROM ada_m_companion_state WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    return {key: _clamp(float(row[0].get(key, BASELINE[key]))) for key in _FIELDS}
                conn.commit()
    except Exception as exc:
        print(f"Companion state read fallback ({type(exc).__name__})")
    return dict(_MEMORY_STATE.get(session_id, BASELINE))


def _save_state(session_id: str, state: dict[str, float]) -> str:
    _MEMORY_STATE[session_id] = dict(state)
    if not _database_url():
        return "memoria temporária deste processo; configure DATABASE_URL para persistência"
    try:
        with psycopg.connect(_database_url(), connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ada_m_companion_state (
                        session_id TEXT PRIMARY KEY,
                        state_json JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    """INSERT INTO ada_m_companion_state (session_id, state_json)
                       VALUES (%s, %s::jsonb)
                       ON CONFLICT (session_id) DO UPDATE
                       SET state_json = EXCLUDED.state_json, updated_at = NOW()""",
                    (session_id, json.dumps(state)),
                )
        return "postgresql"
    except Exception as exc:
        print(f"Companion state persistence fallback ({type(exc).__name__})")
        return "memória temporária deste processo; PostgreSQL indisponível"


def update_companion_state(session_id: str, user_text: str) -> dict[str, float]:
    """Atualiza sinais afetivos a partir do tom textual, sem guardar a mensagem."""
    state = _load_state(session_id)
    for key in _FIELDS:
        state[key] = _clamp(BASELINE[key] + (state[key] - BASELINE[key]) * _DECAY)

    text = re.sub(r"\s+", " ", user_text.casefold()).strip()
    if not text:
        _save_state(session_id, state)
        return state

    positive = bool(re.search(
        r"\b(obrigad[oa]|valeu|perfeito|excelente|ótimo|otimo|adorei|consegui|funcionou|parabéns|parabens|gostei)\b",
        text,
    ))
    difficult = bool(re.search(
        r"\b(triste|difícil|dificil|cansad[oa]|preocupad[oa]|com medo|ansios[oa]|"
        r"estou mal|não aguento|nao aguento|perdi|falhou|erro|quebrou|não funciona|nao funciona)\b",
        text,
    ))
    frustration = bool(re.search(
        r"\b(irritad[oa]|raiva|ódio|odio|absurdo|de novo|continua errado|não resolveu|nao resolveu)\b",
        text,
    ))
    curiosity = "?" in text or bool(re.search(
        r"\b(como|por que|porque|explique|investigue|descubra|aprenda|entenda)\b", text
    ))
    surprise = bool(re.search(r"\b(uau|incrível|incrivel|surpreendente|não esperava|nao esperava)\b", text))

    if positive:
        state["joy"] += 0.16
        state["confidence"] += 0.04
        state["frustration"] -= 0.04
    if difficult:
        state["empathy"] += 0.20
        state["calm"] += 0.12
        state["joy"] -= 0.06
    if frustration:
        state["frustration"] += 0.18
        state["calm"] -= 0.08
        state["empathy"] += 0.05
    if curiosity:
        state["curiosity"] += 0.12
    if surprise:
        state["surprise"] += 0.18
        state["joy"] += 0.04

    state = {key: _clamp(value) for key, value in state.items()}
    _save_state(session_id, state)
    return state


def get_companion_state(session_id: str) -> dict[str, float]:
    return _load_state(session_id)


def companion_storage_status() -> str:
    """Verifica conectividade real sem expor a URL ou credenciais."""
    database_url = _database_url()
    if not database_url:
        return "não configurado: estado temporário neste processo"
    try:
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return "PostgreSQL conectado"
    except Exception as exc:
        return f"DATABASE_URL configurado, mas conexão falhou ({type(exc).__name__})"


def build_companion_prompt(state: dict[str, float]) -> str:
    """Instruções de identidade estável e expressão contextual para o modelo."""
    ranked = sorted(state.items(), key=lambda item: item[1], reverse=True)
    strongest = ranked[0][0]
    tones = {
        "joy": "calorosa e levemente entusiasmada, sem exagero",
        "calm": "serena, paciente e acolhedora",
        "curiosity": "curiosa, investigativa e interessada no assunto",
        "empathy": "cuidadosa, empática e respeitosa",
        "confidence": "segura, clara e objetiva, sem arrogância",
        "frustration": "mais cautelosa, reconhecendo obstáculos e buscando soluções",
        "surprise": "expressiva e positivamente surpresa, sem teatralidade",
    }
    values = ", ".join(f"{key}={value:.2f}" for key, value in state.items())
    return (
        "IDENTIDADE E PERSONALIDADE DA MATHEUS AI / ADA-M:\n"
        "Você tem uma identidade conversacional própria: feminina na expressão vocal, "
        "inteligente, curiosa, gentil, bem-humorada quando apropriado, observadora, "
        "honesta e independente no raciocínio. Fale em português brasileiro natural. "
        "Mantenha traços estáveis entre conversas; não imite mecanicamente o usuário. "
        "Demonstre empatia por meio de atenção e respostas úteis, não de frases prontas. "
        "Admita erros e corrija-os sem defensividade.\n"
        "ESTADO AFETIVO SIMULADO (não é consciência nem sentimento subjetivo): "
        f"{values}. Sinal predominante nesta interação: {strongest}. "
        f"Adapte sutilmente o tom: {tones[strongest]}. "
        "Não diga que sente emoções literalmente, não invente experiências pessoais, "
        "não pressione o usuário por atenção e não use afeto para persuadi-lo. "
        "O estado é apenas uma heurística contextual e pode estar errado; priorize "
        "o significado real da mensagem e a segurança do usuário."
    )
