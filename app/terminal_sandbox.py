"""Terminal execution for ADA-M through its private VPS executor.

When ADA_EXECUTOR_URL is configured, commands run on the user's VPS through
Cloudflare Access and the executor's own bearer token. Render Sandboxes remain
available as a backward-compatible fallback.
"""
from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any

import httpx

MAX_COMMAND_CHARS = 4000
MAX_OUTPUT_CHARS = 10000
COMMAND_TIMEOUT_SECONDS = 45
SANDBOX_RUNTIME_SECONDS = 3600
SANDBOX_IDLE_SECONDS = 900
WORKSPACE = "/home/render/ada-workspace"

NETWORK_ALLOWED_DOMAINS = (
    "github.com", "codeload.github.com", "*.githubusercontent.com",
    "pypi.org", "*.pythonhosted.org", "registry.npmjs.org", "npmjs.com",
    "*.npmjs.com", "deb.debian.org", "archive.ubuntu.com", "security.ubuntu.com",
)


def _vps_settings() -> tuple[str, dict[str, str]] | None:
    """Return the private VPS endpoint and auth headers when fully configured."""
    url = os.getenv("ADA_EXECUTOR_URL", "").strip().rstrip("/")
    if not url:
        return None
    token = os.getenv("ADA_EXECUTOR_TOKEN", "").strip()
    client_id = os.getenv("CF_ACCESS_CLIENT_ID", "").strip()
    client_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "").strip()
    if not all((token, client_id, client_secret)):
        return None
    return url, {
        "Authorization": f"Bearer {token}",
        "CF-Access-Client-Id": client_id,
        "CF-Access-Client-Secret": client_secret,
    }


def is_terminal_configured() -> bool:
    """True when the VPS executor or the legacy Render sandbox is configured."""
    if os.getenv("ADA_EXECUTOR_URL", "").strip():
        return _vps_settings() is not None
    return bool(os.getenv("RENDER_API_KEY", "").strip() and os.getenv("RENDER_WORKSPACE_ID", "").strip())


def validate_command(command: Any) -> str:
    if not isinstance(command, str):
        raise ValueError("O comando precisa ser texto.")
    value = command.strip()
    if not value:
        raise ValueError("Informe um comando para executar.")
    if len(value) > MAX_COMMAND_CHARS:
        raise ValueError(f"O comando excede o limite de {MAX_COMMAND_CHARS} caracteres.")
    if "\x00" in value:
        raise ValueError("O comando contém um caractere inválido.")
    return value


async def _run_on_vps(command: str) -> dict[str, Any]:
    settings = _vps_settings()
    if settings is None:
        return {
            "ok": False,
            "error": (
                "O VPS foi selecionado, mas faltam variáveis no serviço ADA-M do Render: "
                "ADA_EXECUTOR_TOKEN, CF_ACCESS_CLIENT_ID e CF_ACCESS_CLIENT_SECRET."
            ),
        }
    base_url, headers = settings
    timeout_seconds = min(max(int(os.getenv("ADA_EXECUTOR_TIMEOUT", "50")), 1), 55)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds + 12, connect=12)) as client:
            response = await client.post(
                f"{base_url}/execute",
                headers=headers,
                json={"command": command, "timeout": timeout_seconds},
            )
        if response.status_code in (401, 403):
            return {
                "ok": False,
                "error": (
                    f"O Cloudflare/VPS recusou a autenticação (HTTP {response.status_code}). "
                    "Confira o Service Token do Cloudflare Access e ADA_EXECUTOR_TOKEN no Render."
                ),
            }
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Resposta inválida do executor VPS.")
        returncode = int(payload.get("returncode", 1))
        return {
            "ok": returncode == 0,
            "exit_code": returncode,
            "stdout": str(payload.get("stdout") or "")[:MAX_OUTPUT_CHARS],
            "stderr": str(payload.get("stderr") or "")[:MAX_OUTPUT_CHARS],
            "workspace": "/home/ada-runner/workspace",
            "timeout_seconds": timeout_seconds,
            "executor": "VPS",
            "session_note": "Terminal conectado ao VPS; arquivos ficam no workspace persistente do servidor.",
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": "O VPS demorou além do limite para responder. Confira se ada-executor está ativo."}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"O executor VPS respondeu com HTTP {exc.response.status_code}."}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"ok": False, "error": f"Não foi possível comunicar com o executor VPS ({type(exc).__name__})."}


def _network_policy():
    """Build the typed policy objects required by Render SDK 1.9+."""
    from render.sandbox import EgressRule, NetworkPolicy
    return NetworkPolicy(type="allow-list", rules=[EgressRule(domain=domain) for domain in NETWORK_ALLOWED_DOMAINS])


def _client():
    from render import RenderAsync
    return RenderAsync(token=os.getenv("RENDER_API_KEY", "").strip(), owner_id=os.getenv("RENDER_WORKSPACE_ID", "").strip())


async def _run_in_sandbox(client, sandbox_id: str, command: str) -> dict[str, Any]:
    from render.sandbox import SandboxExecExit, SandboxExecOutput
    script = f"mkdir -p {shlex.quote(WORKSPACE)} && cd {shlex.quote(WORKSPACE)} && {command}"
    wrapped = f"timeout -k 3 {COMMAND_TIMEOUT_SECONDS}s bash -lc {shlex.quote(script)}"
    stdout: list[str] = []
    stderr: list[str] = []
    exit_code: int | None = None
    collected = 0
    async for event in client.sandboxes.exec(sandbox_id, wrapped):
        if isinstance(event, SandboxExecOutput):
            chunk = str(event.data or "")
            remaining = max(0, MAX_OUTPUT_CHARS - collected)
            if remaining:
                clipped = chunk[:remaining]
                (stderr if event.stream == "stderr" else stdout).append(clipped)
                collected += len(clipped)
        elif isinstance(event, SandboxExecExit):
            exit_code = int(event.exit_code)
    if exit_code is None:
        return {"ok": False, "error": "A execução terminou sem um código de saída confirmado.", "stdout": "".join(stdout), "stderr": "".join(stderr)}
    out, err = "".join(stdout), "".join(stderr)
    if len(out) + len(err) >= MAX_OUTPUT_CHARS:
        err += "\n[saída truncada pelo limite de segurança]"
    return {"ok": exit_code == 0, "exit_code": exit_code, "stdout": out, "stderr": err, "workspace": WORKSPACE, "timeout_seconds": COMMAND_TIMEOUT_SECONDS}


async def run_terminal_command(session: dict[str, Any], command: Any) -> dict[str, Any]:
    """Execute on the VPS when configured; otherwise preserve Render sandbox."""
    try:
        clean_command = validate_command(command)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if os.getenv("ADA_EXECUTOR_URL", "").strip():
        return await _run_on_vps(clean_command)
    if not is_terminal_configured():
        return {
            "ok": False,
            "error": (
                "Terminal não configurado. Configure ADA_EXECUTOR_URL, ADA_EXECUTOR_TOKEN, "
                "CF_ACCESS_CLIENT_ID e CF_ACCESS_CLIENT_SECRET no serviço ADA-M do Render."
            ),
        }
    stage = "initializing Render SDK client"
    try:
        client = _client()
        sandbox_id = str(session.get("ada_terminal_sandbox_id") or "")
        reused = bool(sandbox_id)
        if sandbox_id:
            stage = "retrieving existing sandbox"
            try:
                sandbox = await client.sandboxes.from_id(sandbox_id)
                if sandbox.status in {"terminated", "errored"}:
                    sandbox_id, reused = "", False
            except Exception as exc:
                if type(exc).__name__ in {"SandboxNotFoundError", "SandboxNotRunningError"}:
                    sandbox_id, reused = "", False
                else:
                    raise
        if not sandbox_id:
            stage = "creating sandbox"
            sandbox = await client.sandboxes.create(
                plan="1c-2g", timeout_seconds=SANDBOX_RUNTIME_SECONDS,
                idle_timeout_seconds=SANDBOX_IDLE_SECONDS,
                network_policy=_network_policy(), wait=True,
            )
            sandbox_id = sandbox.id
            session["ada_terminal_sandbox_id"] = sandbox_id
        stage = "executing command in sandbox"
        result = await asyncio.wait_for(_run_in_sandbox(client, sandbox_id, clean_command), timeout=COMMAND_TIMEOUT_SECONDS + 25)
        result["sandbox_reused"] = reused
        result["session_note"] = "Workspace isolado desta sessão; os arquivos persistem até a sessão expirar."
        return result
    except asyncio.TimeoutError:
        return {"ok": False, "error": "A resposta do terminal excedeu o limite de espera. O comando remoto tem limite próprio de 45 segundos; confira o estado antes de repetir ações."}
    except Exception as exc:
        detail = str(exc).strip().replace("\n", " ")[:500]
        print(f"[terminal] sandbox operation failed stage={stage!r} error={type(exc).__name__} detail={detail!r}")
        return {"ok": False, "error": f"Falha no terminal isolado durante '{stage}' ({type(exc).__name__}: {detail or 'sem detalhes'}). Consulte os logs do serviço ADA-M no Render."}
