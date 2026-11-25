import pytest

from app import terminal_sandbox


@pytest.mark.asyncio
async def test_virtual_admin_command_routes_only_to_fixed_install_job(monkeypatch):
    called = []

    async def fake_install():
        called.append(True)
        return {"ok": True, "status": "started", "completion_confirmed": False}

    monkeypatch.setattr(terminal_sandbox, "_request_vps_admin_install_tools", fake_install)

    result = await terminal_sandbox.run_terminal_command({}, "ada-admin install-tools")

    assert called == [True]
    assert result["ok"] is True
    assert result["status"] == "started"
    assert result["completion_confirmed"] is False


@pytest.mark.asyncio
async def test_virtual_admin_command_rejects_unapproved_operations(monkeypatch):
    async def must_not_run():
        raise AssertionError("admin route must not be called")

    monkeypatch.setattr(terminal_sandbox, "_request_vps_admin_install_tools", must_not_run)

    result = await terminal_sandbox.run_terminal_command({}, "ada-admin install-anything")

    assert result["ok"] is False
    assert "não autorizada" in result["error"].lower()


@pytest.mark.asyncio
async def test_admin_install_request_uses_vps_bearer_auth_only(monkeypatch):
    monkeypatch.setenv("ADA_EXECUTOR_URL", "https://executor.example.test/")
    monkeypatch.setenv("ADA_EXECUTOR_TOKEN", "internal-test-token")
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "started",
                "message": "Instalação administrativa solicitada.",
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

    result = await terminal_sandbox.run_terminal_command({}, "ada-admin install-tools")

    assert captured["url"] == "https://executor.example.test/admin/install-tools"
    assert captured["headers"]["Authorization"] == "Bearer internal-test-token"
    assert captured["json"] == {}
    assert result["ok"] is True
    assert result["status"] == "started"
    assert result["completion_confirmed"] is False
