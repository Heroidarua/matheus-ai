import pytest

from app import terminal_sandbox


def test_validate_command_accepts_shell_text():
    assert terminal_sandbox.validate_command("  pwd && ls -la  ") == "pwd && ls -la"


@pytest.mark.parametrize("value", ["", "   ", None, 12, "x" * 4001, "pwd\x00ls"])
def test_validate_command_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        terminal_sandbox.validate_command(value)


def test_terminal_is_disabled_without_render_credentials(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    monkeypatch.delenv("RENDER_WORKSPACE_ID", raising=False)
    assert not terminal_sandbox.is_terminal_configured()


def test_terminal_requires_both_render_credentials(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test")
    monkeypatch.delenv("RENDER_WORKSPACE_ID", raising=False)
    assert not terminal_sandbox.is_terminal_configured()
    monkeypatch.setenv("RENDER_WORKSPACE_ID", "tea_test")
    assert terminal_sandbox.is_terminal_configured()



def test_vps_terminal_uses_all_three_auth_headers(monkeypatch):
    monkeypatch.setenv("ADA_EXECUTOR_URL", "https://executor.example.test")
    monkeypatch.setenv("ADA_EXECUTOR_TOKEN", "internal-test-token")
    monkeypatch.setenv("CF_ACCESS_CLIENT_ID", "client-id")
    monkeypatch.setenv("CF_ACCESS_CLIENT_SECRET", "client-secret")
    settings = terminal_sandbox._vps_settings()
    assert settings is not None
    url, headers = settings
    assert url == "https://executor.example.test"
    assert headers["Authorization"] == "Bearer internal-test-token"
    assert headers["CF-Access-Client-Id"] == "client-id"
    assert headers["CF-Access-Client-Secret"] == "client-secret"
    assert terminal_sandbox.is_terminal_configured()


def test_vps_terminal_is_not_configured_when_any_auth_value_is_missing(monkeypatch):
    monkeypatch.setenv("ADA_EXECUTOR_URL", "https://executor.example.test")
    monkeypatch.setenv("ADA_EXECUTOR_TOKEN", "internal-test-token")
    monkeypatch.setenv("CF_ACCESS_CLIENT_ID", "client-id")
    monkeypatch.delenv("CF_ACCESS_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test")
    monkeypatch.setenv("RENDER_WORKSPACE_ID", "tea_test")
    assert terminal_sandbox._vps_settings() is None
    assert not terminal_sandbox.is_terminal_configured()


@pytest.mark.asyncio
async def test_vps_executor_posts_real_command_and_returns_real_output(monkeypatch):
    monkeypatch.setenv("ADA_EXECUTOR_URL", "https://executor.example.test/")
    monkeypatch.setenv("ADA_EXECUTOR_TOKEN", "internal-test-token")
    monkeypatch.setenv("CF_ACCESS_CLIENT_ID", "client-id")
    monkeypatch.setenv("CF_ACCESS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("ADA_EXECUTOR_TIMEOUT", "37")

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "returncode": 0,
                "stdout": "/home/ada-runner/workspace\\n",
                "stderr": "",
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(terminal_sandbox.httpx, "AsyncClient", FakeAsyncClient)

    result = await terminal_sandbox.run_terminal_command({}, "pwd")

    assert captured["url"] == "https://executor.example.test/execute"
    assert captured["headers"]["Authorization"] == "Bearer internal-test-token"
    assert captured["headers"]["CF-Access-Client-Id"] == "client-id"
    assert captured["headers"]["CF-Access-Client-Secret"] == "client-secret"
    assert captured["json"] == {"command": "pwd", "timeout": 37}
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "/home/ada-runner/workspace\\n"
    assert result["workspace"] == "/home/ada-runner/workspace"
    assert result["executor"] == "VPS"


@pytest.mark.asyncio
async def test_vps_executor_reports_nonzero_exit_code_without_faking_success(monkeypatch):
    monkeypatch.setenv("ADA_EXECUTOR_URL", "https://executor.example.test")
    monkeypatch.setenv("ADA_EXECUTOR_TOKEN", "internal-test-token")
    monkeypatch.setenv("CF_ACCESS_CLIENT_ID", "client-id")
    monkeypatch.setenv("CF_ACCESS_CLIENT_SECRET", "client-secret")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"returncode": 127, "stdout": "", "stderr": "nmap: not found"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(terminal_sandbox.httpx, "AsyncClient", FakeAsyncClient)

    result = await terminal_sandbox.run_terminal_command({}, "nmap --version")

    assert result["ok"] is False
    assert result["exit_code"] == 127
    assert result["stderr"] == "nmap: not found"
