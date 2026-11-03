from app import bryan_adaptation


def test_explicit_user_instruction_changes_bryan_participation_mode(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    bryan_adaptation._VOLATILE.clear()

    result = bryan_adaptation.learn_preference("session:bryan", "Bryan, fala mais e participe mais!")

    assert result == {"updated": True, "participation_mode": "proactive"}
    assert bryan_adaptation.get_profile("session:bryan")["participation_mode"] == "proactive"


def test_quiet_instruction_is_persisted_and_isolated_by_session(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    bryan_adaptation._VOLATILE.clear()

    bryan_adaptation.learn_preference("session-a:bryan", "Bryan, fica quieto e não interrompa.")
    bryan_adaptation.learn_preference("session-b:bryan", "Bryan, pode participar mais.")

    assert bryan_adaptation.get_profile("session-a:bryan")["participation_mode"] == "quiet"
    assert bryan_adaptation.get_profile("session-b:bryan")["participation_mode"] == "proactive"


def test_ambiguous_message_does_not_change_preference(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    bryan_adaptation._VOLATILE.clear()
    bryan_adaptation.set_profile("session:bryan", "quiet")

    result = bryan_adaptation.learn_preference("session:bryan", "Hoje estou trabalhando no meu projeto.")

    assert result == {"updated": False, "participation_mode": "quiet"}


def test_reset_returns_to_balanced_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    bryan_adaptation._VOLATILE.clear()
    bryan_adaptation.set_profile("session:bryan", "proactive")

    assert bryan_adaptation.delete_profile("session:bryan") is True
    assert bryan_adaptation.get_profile("session:bryan")["participation_mode"] == "balanced"
