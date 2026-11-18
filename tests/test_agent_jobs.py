import pytest

from app import agent_jobs


def test_job_checkpoint_and_history_are_scoped_to_owner(monkeypatch):
    monkeypatch.setattr(agent_jobs, "_db", lambda: None)
    owner = "session-one"
    job_id = agent_jobs.create_job(owner, "Auditar meu site", {
        "messages": [{"role": "user", "content": "Auditar meu site"}],
        "terminal_calls_total": 2,
        "events": [{"command": "nmap -p 80,443 example.test", "ok": True}],
    })
    pending = agent_jobs.get_pending_job(owner)
    assert pending is not None
    assert pending["id"] == job_id
    assert pending["state"]["terminal_calls_total"] == 2
    assert agent_jobs.get_pending_job("another-session") is None

    agent_jobs.save_job(owner, job_id, "Auditar meu site", "paused", {
        "messages": [{"role": "assistant", "content": "Parei no checkpoint."}],
        "terminal_calls_total": 6,
        "events": [{"command": "nmap -p 80,443 example.test", "ok": True}],
    })
    history = agent_jobs.list_jobs(owner)
    assert history[0]["status"] == "paused"
    assert history[0]["state"]["terminal_calls_total"] == 6


def test_completed_jobs_are_not_returned_as_pending(monkeypatch):
    monkeypatch.setattr(agent_jobs, "_db", lambda: None)
    owner = "session-completed"
    job_id = agent_jobs.create_job(owner, "Verificar versão", {"messages": []})
    agent_jobs.save_job(owner, job_id, "Verificar versão", "completed", {"messages": []})
    assert agent_jobs.get_pending_job(owner) is None


def test_checkpoint_redacts_secrets(monkeypatch):
    monkeypatch.setattr(agent_jobs, "_db", lambda: None)
    owner = "session-secret"
    job_id = agent_jobs.create_job(owner, "Teste seguro", {
        "messages": [{"role": "user", "content": "Authorization: Bearer abcdefghijklmnop"}],
    })
    saved = agent_jobs.get_pending_job(owner)
    assert "[REDACTED]" in saved["state"]["messages"][0]["content"]
    assert "abcdefghijklmnop" not in saved["state"]["messages"][0]["content"]


@pytest.mark.parametrize("message", [
    "continuar", "Continue de onde parou", "retomar tarefa", "/continuar",
    "pode continuar", "prossiga",
])
def test_detects_agent_continuation_request(message):
    assert agent_jobs.is_agent_continuation_request(message)


@pytest.mark.parametrize("message", [
    "continue explicando o que é Linux",
    "quero continuar um novo projeto",
    "como retomar uma tarefa?",
    "continuar agora com outra coisa",
])
def test_does_not_overmatch_agent_continuation_request(message):
    assert not agent_jobs.is_agent_continuation_request(message)
