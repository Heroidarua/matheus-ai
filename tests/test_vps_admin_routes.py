import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "ada-executor"
    / "admin_routes.py"
)
SPEC = importlib.util.spec_from_file_location("ada_admin_routes_under_test", MODULE_PATH)
admin_routes = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(admin_routes)


class FakeProcess:
    def __init__(self, returncode=0, stdout=b"diagnostic-output", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def route_endpoints(token_validator):
    router = admin_routes.create_admin_router(token_validator)
    return {route.path: route.endpoint for route in router.routes}


@pytest.mark.asyncio
async def test_diagnostics_route_runs_only_fixed_read_only_operation(monkeypatch):
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess(stdout=b"hostname=test-vps\n")

    monkeypatch.setattr(admin_routes.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    endpoints = route_endpoints(lambda value: value == "Bearer valid")

    result = await endpoints["/admin/diagnostics"](authorization="Bearer valid")

    assert captured["args"] == ("sudo", "-n", "/usr/local/sbin/ada-admin", "diagnostics")
    assert result == {
        "ok": True,
        "operation": "diagnostics",
        "output": "hostname=test-vps\n",
    }


@pytest.mark.asyncio
async def test_install_status_route_uses_fixed_operation(monkeypatch):
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProcess(stdout=b"Result=success\n")

    monkeypatch.setattr(admin_routes.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    endpoints = route_endpoints(lambda value: value == "Bearer valid")

    result = await endpoints["/admin/install-tools/status"](authorization="Bearer valid")

    assert captured["args"][-1] == "install-tools-status"
    assert result["output"] == "Result=success\n"


@pytest.mark.asyncio
async def test_admin_routes_reject_invalid_bearer_token_before_execution(monkeypatch):
    async def must_not_run(*args, **kwargs):
        raise AssertionError("sudo must not run without a valid token")

    monkeypatch.setattr(admin_routes.asyncio, "create_subprocess_exec", must_not_run)
    endpoints = route_endpoints(lambda value: False)

    with pytest.raises(HTTPException) as exc:
        await endpoints["/admin/diagnostics"](authorization="Bearer invalid")

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_route_reports_nonzero_exit_without_claiming_success(monkeypatch):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess(returncode=1, stderr=b"operation failed")

    monkeypatch.setattr(admin_routes.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    endpoints = route_endpoints(lambda value: True)

    with pytest.raises(HTTPException) as exc:
        await endpoints["/admin/diagnostics"](authorization="Bearer valid")

    assert exc.value.status_code == 500
    assert exc.value.detail == "operation failed"
