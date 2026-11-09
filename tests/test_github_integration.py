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
