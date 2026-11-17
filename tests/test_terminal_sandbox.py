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
