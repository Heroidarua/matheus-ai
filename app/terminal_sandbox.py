"""Isolated command execution for ADA-M using Render Sandboxes.

Untrusted commands run in disposable Linux microVMs. Render API credentials
stay in the ADA-M service and are never injected into the sandbox.
"""
from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any

MAX_COMMAND_CHARS = 4000
MAX_OUTPUT_CHARS = 10000
COMMAND_TIMEOUT_SECONDS = 45
SANDBOX_RUNTIME_SECONDS = 3600
SANDBOX_IDLE_SECONDS = 900
WORKSPACE = "/home/render/ada-workspace"

# Restrict outbound HTTPS to common source-control and package registries.
NETWORK_POLICY = {
    "type": "allow-list",
    "rules": [
        {"domain": "github.com"},
        {"domain": "codeload.github.com"},
        {"domain": "*.githubusercontent.com"},
        {"domain": "pypi.org"},
        {"domain": "*.pythonhosted.org"},
        {"domain": "registry.npmjs.org"},
        {"domain": "npmjs.com"},
        {"domain": "*.npmjs.com"},
        {"domain": "deb.debian.org"},
        {"domain": "archive.ubuntu.com"},
        {"domain": "security.ubuntu.com"},
    ],
}


def is_terminal_configured() -> bool:
    """True only when both Render credentials exist in the ADA-M host."""
    return bool(
        os.getenv("RENDER_API_KEY", "").strip()
        and os.getenv("RENDER_WORKSPACE_ID", "").strip()
    )


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


def _client():
    # Import lazy so the application can start with terminal integration off.
    from render import RenderAsync

    return RenderAsync(
        token=os.getenv("RENDER_API_KEY", "").strip(),
        owner_id=os.getenv("RENDER_WORKSPACE_ID", "").strip(),
    )


async def _run_in_sandbox(sandbox_id: str, command: str) -> dict[str, Any]:
    from render.sandbox import SandboxExecExit, SandboxExecOutput

    client = _client()
    script = (
        f"mkdir -p {shlex.quote(WORKSPACE)} && "
        f"cd {shlex.quote(WORKSPACE)} && {command}"
    )
    wrapped = (
        f"timeout -k 3 {COMMAND_TIMEOUT_SECONDS}s bash -lc "
        f"{shlex.quote(script)}"
    )
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
        return {
            "ok": False,
            "error": "A execução terminou sem um código de saída confirmado.",
            "stdout": "".join(stdout),
            "stderr": "".join(stderr),
        }

    out = "".join(stdout)
    err = "".join(stderr)
    if len(out) + len(err) >= MAX_OUTPUT_CHARS:
        err += "\n[saída truncada pelo limite de segurança]"
    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "stdout": out,
        "stderr": err,
        "workspace": WORKSPACE,
        "timeout_seconds": COMMAND_TIMEOUT_SECONDS,
    }


async def run_terminal_command(session: dict[str, Any], command: Any) -> dict[str, Any]:
    """Run one command in the caller's persistent, isolated sandbox session."""
    try:
        clean_command = validate_command(command)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not is_terminal_configured():
        return {
            "ok": False,
            "error": (
                "Terminal isolado não configurado. No Render, adicione RENDER_API_KEY "
                "e RENDER_WORKSPACE_ID ao serviço principal da ADA-M."
            ),
        }

    try:
        client = _client()
        sandbox_id = str(session.get("ada_terminal_sandbox_id") or "")
        reused = bool(sandbox_id)
        if sandbox_id:
            try:
                sandbox = await client.sandboxes.from_id(sandbox_id)
                if sandbox.status in {"terminated", "errored"}:
                    sandbox_id = ""
                    reused = False
            except Exception as exc:
                if type(exc).__name__ in {"SandboxNotFoundError", "SandboxNotRunningError"}:
                    sandbox_id = ""
                    reused = False
                else:
                    raise

        if not sandbox_id:
            sandbox = await client.sandboxes.create(
                plan="1c-2g",
                timeout_seconds=SANDBOX_RUNTIME_SECONDS,
                idle_timeout_seconds=SANDBOX_IDLE_SECONDS,
                network_policy=NETWORK_POLICY,
                wait=True,
            )
            sandbox_id = sandbox.id
            session["ada_terminal_sandbox_id"] = sandbox_id

        result = await asyncio.wait_for(
            _run_in_sandbox(sandbox_id, clean_command),
            timeout=COMMAND_TIMEOUT_SECONDS + 25,
        )
        result["sandbox_reused"] = reused
        result["session_note"] = (
            "Workspace isolado desta sessão; os arquivos persistem até a sessão expirar."
        )
        return result
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": (
                "A resposta do terminal excedeu o limite de espera. O comando remoto "
                "tem limite próprio de 45 segundos; confira o estado antes de repetir ações."
            ),
        }
    except Exception as exc:
        print(f"[terminal] sandbox operation failed ({type(exc).__name__})")
        return {
            "ok": False,
            "error": (
                f"Falha no terminal isolado ({type(exc).__name__}). "
                "Confira as credenciais, o workspace e os limites do Render."
            ),
        }
