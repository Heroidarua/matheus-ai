import time

import pytest

from app import github_integration as github


def test_chat_requested_path_extracts_supported_repository_files():
    assert github._chat_requested_path("Analise o arquivo app/main.py") == "app/main.py"
    assert github._chat_requested_path("Veja README.md e requirements.txt") == "README.md"
    assert github._chat_requested_path("Explique o que é Python") is None


def test_chat_requested_path_rejects_git_metadata_paths():
    assert github._chat_requested_path("Leia .git/config") is None


@pytest.mark.asyncio
async def test_installation_token_requests_only_required_permissions(monkeypatch):
    captured = {}

    def fake_jwt():
        return "signed-app-jwt"

    async def fake_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {"token": "short-lived-installation-token"}

    monkeypatch.setattr(github, "_app_jwt", fake_jwt)
    monkeypatch.setattr(github, "_github_request", fake_request)

    token = await github._installation_token(123, write=True, pull_requests=True)

    assert token == "short-lived-installation-token"
    assert captured["method"] == "POST"
    assert captured["path"] == "/app/installations/123/access_tokens"
    assert captured["json_body"] == {
        "permissions": {"contents": "write", "pull_requests": "write"}
    }


@pytest.mark.asyncio
async def test_chat_context_explains_when_github_is_not_connected():
    class FakeRequest:
        session = {}

    result = await github.github_chat_context(FakeRequest(), "Analise meu repositório no GitHub")

    assert "ainda não está conectado" in result
    assert "Conectar GitHub" in result


@pytest.mark.asyncio
async def test_chat_context_ignores_messages_without_github_intent():
    class FakeRequest:
        session = {}

    result = await github.github_chat_context(FakeRequest(), "Como faço uma função em Python?")

    assert result == ""


@pytest.mark.asyncio
async def test_installation_token_can_scope_repository_creation_permission(monkeypatch):
    captured = {}

    monkeypatch.setattr(github, "_app_jwt", lambda: "signed-app-jwt")

    async def fake_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {"token": "short-lived-installation-token"}

    monkeypatch.setattr(github, "_github_request", fake_request)
    token = await github._installation_token(123, write=True, repository_admin=True)

    assert token == "short-lived-installation-token"
    assert captured["json_body"] == {
        "permissions": {"contents": "write", "administration": "write"}
    }


@pytest.mark.asyncio
async def test_confirm_new_project_creates_private_repo_and_uploads_files(monkeypatch):
    calls = []

    class FakeRequest:
        session = {"github_installation_id": 123, "github_account": "Heroidarua"}
        headers = {}

    request = FakeRequest()
    proposal_id = "proposal-token-long-enough-for-validation"
    github.PENDING_PROJECTS[proposal_id] = {
        "owner": "session-owner",
        "installation_id": 123,
        "account": "Heroidarua",
        "name": "ada-test-project",
        "description": "Projeto de teste",
        "files": [{"path": "app.py", "content": "print('hello')"}],
        "created_at": 1,
        "expires_at": time.time() + 300,
    }

    monkeypatch.setattr(github, "_same_origin", lambda request: None)
    monkeypatch.setattr(github, "_session_owner", lambda request: "session-owner")

    async def fake_token(*args, **kwargs):
        return "installation-token"

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "POST" and path == "/user/repos":
            return {
                "full_name": "Heroidarua/ada-test-project",
                "default_branch": "main",
                "html_url": "https://github.com/Heroidarua/ada-test-project",
            }
        return {}

    monkeypatch.setattr(github, "_installation_token", fake_token)
    monkeypatch.setattr(github, "_github_request", fake_request)

    result = await github.confirm_new_project(
        github.ConfirmNewProject(proposal_id=proposal_id), request
    )

    assert result["ok"] is True
    assert result["private"] is True
    assert result["url"] == "https://github.com/Heroidarua/ada-test-project"
    create_call = next(call for call in calls if call[0] == "POST" and call[1] == "/user/repos")
    assert create_call[2]["json_body"]["private"] is True
    assert create_call[2]["json_body"]["auto_init"] is True
    assert any(call[0] == "PUT" and call[1] == "/repos/Heroidarua/ada-test-project/contents/app.py" for call in calls)
    assert proposal_id not in github.PENDING_PROJECTS
