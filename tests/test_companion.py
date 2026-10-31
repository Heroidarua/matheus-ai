import pytest

from app import companion


def test_state_starts_from_personality_baseline(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    state = companion.update_companion_state("test-session-baseline", "Olá.")
    assert state["calm"] == companion.BASELINE["calm"]
    assert state["joy"] == companion.BASELINE["joy"]


def test_positive_feedback_increases_joy(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    state = companion.update_companion_state("test-session-positive", "Obrigado, funcionou perfeitamente!")
    assert state["joy"] > companion.BASELINE["joy"]
    assert state["confidence"] > companion.BASELINE["confidence"]


def test_empathy_signal_increases_empathy_and_calm(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    state = companion.update_companion_state("test-session-empathy", "Estou triste e preocupado.")
    assert state["empathy"] > companion.BASELINE["empathy"]
    assert state["calm"] > companion.BASELINE["calm"]


def test_questions_increase_curiosity(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    state = companion.update_companion_state("test-session-curiosity", "Como isso funciona?")
    assert state["curiosity"] > companion.BASELINE["curiosity"]


def test_persona_prompt_discloses_simulated_state():
    prompt = companion.build_companion_prompt(dict(companion.BASELINE))
    assert "IDENTIDADE E PERSONALIDADE" in prompt
    assert "não é consciência" in prompt
    assert "português brasileiro natural" in prompt


def test_raw_user_text_is_not_stored(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    secret_text = "mensagem privada que não deve ser persistida"
    companion.update_companion_state("test-session-private", secret_text)
    assert secret_text not in repr(companion._MEMORY_STATE)
