from app import long_term_memory


def test_bryan_memory_is_isolated_from_ada_m_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    long_term_memory._VOLATILE.clear()
    session_id = "shared-session"

    long_term_memory.remember(
        f"{session_id}:bryan",
        "Meu projeto de personagem Bryan usa memória contextual própria.",
    )
    long_term_memory.remember(
        session_id,
        "Prefiro respostas diretas e instruções passo a passo.",
    )

    bryan_items = long_term_memory.list_memories(f"{session_id}:bryan")
    ada_items = long_term_memory.list_memories(session_id)

    assert len(bryan_items) == 1
    assert "Bryan" in bryan_items[0]
    assert len(ada_items) == 1
    assert "Prefiro respostas" in ada_items[0]

    assert long_term_memory.forget_all(f"{session_id}:bryan") == 1
    assert long_term_memory.list_memories(session_id) == ada_items


def test_bryan_memory_keeps_existing_sensitive_data_filter(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    long_term_memory._VOLATILE.clear()

    saved = long_term_memory.remember(
        "private-session:bryan",
        "Minha senha é exemplo-super-secreto-123 e nunca deve ser compartilhada.",
    )

    assert saved is False
    assert long_term_memory.list_memories("private-session:bryan") == []
