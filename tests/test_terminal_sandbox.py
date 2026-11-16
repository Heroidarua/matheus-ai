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
