"""Terminal execution for ADA-M through its private VPS executor.

Commands run locally on the same VPS through the private loopback interface,
authenticated with the executor's bearer token. No Render or Cloudflare Access
sandbox fallback is used.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

MAX_COMMAND_CHARS = 4000
MAX_OUTPUT_CHARS = 100000
COMMAND_TIMEOUT_SECONDS = 45
WORKSPACE = "/home/ada-runner/workspace"

NETWORK_ALLOWED_DOMAINS = (
    "github.com", "codeload.github.com", "*.githubusercontent.com",
    "pypi.org", "*.pythonhosted.org", "registry.npmjs.org", "npmjs.com",
    "*.npmjs.com", "deb.debian.org", "archive.ubuntu.com", "security.ubuntu.com",
)


def _vps_settings() -> tuple[str, dict[str, str]] | None:
    """Return the local VPS executor endpoint and its bearer authentication."""
    url = os.getenv("ADA_EXECUTOR_URL", "").strip().rstrip("/")
    token = os.getenv("ADA_EXECUTOR_TOKEN", "").strip()
    if not url or not token:
        return None
    return url, {"Authorization": f"Bearer {token}"}


def is_terminal_configured() -> bool:
    """The terminal is configured only when the VPS executor is available."""
    return _vps_settings() is not None


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


async def _run_on_vps(command: str, on_event=None) -> dict[str, Any]:
    """Stream command output from the VPS executor while preserving bounded output."""
    settings = _vps_settings()
    if settings is None:
        return {
            "ok": False,
            "error": (
                "Executor da VPS não configurado. Defina ADA_EXECUTOR_URL e ADA_EXECUTOR_TOKEN no /opt/ada-m/.env."
            ),
        }
    base_url, headers = settings
    timeout_seconds = min(max(int(os.getenv("ADA_EXECUTOR_TIMEOUT", "50")), 1), 55)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    collected = 0
    output_truncated = False
    exit_code: int | None = None
    stream_error: str | None = None

    async def emit(event: dict[str, Any]) -> None:
        if on_event is not None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result

    try:
        timeout = httpx.Timeout(
            timeout_seconds + 15,
            connect=12,
            read=timeout_seconds + 15,
            write=12,
            pool=12,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url}/execute/stream",
                headers=headers,
                json={"command": command, "timeout": timeout_seconds},
            ) as response:
                if response.status_code in (401, 403):
                    return {
                        "ok": False,
                        "error": (
                            f"O executor da VPS recusou o token (HTTP {response.status_code}). Confira ADA_EXECUTOR_TOKEN com /opt/ada-executor/.token."
                        ),
                    }
                response.raise_for_status()
                event_name = "message"
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if event_name == "start":
                        await emit({"event": "start", **payload})
                    elif event_name == "output":
                        stream_name = "stderr" if payload.get("stream") == "stderr" else "stdout"
                        chunk = str(payload.get("text") or "")
                        remaining = max(0, MAX_OUTPUT_CHARS - collected)
                        if len(chunk) > remaining:
                            output_truncated = True
                        if remaining:
                            chunk = chunk[:remaining]
                            (stderr_parts if stream_name == "stderr" else stdout_parts).append(chunk)
                            collected += len(chunk)
                            if chunk:
                                await emit({"event": "output", "stream": stream_name, "text": chunk})
                    elif event_name == "complete":
                        exit_code = int(payload.get("returncode", 1))
                        await emit({"event": "complete", "returncode": exit_code})
                    elif event_name == "error":
                        stream_error = str(payload.get("message") or "Falha durante a execução na VPS.")
                        await emit({"event": "error", "message": stream_error})

        stdout = "".join(stdout_parts)
        stderr = "".join(stderr_parts)
        if output_truncated:
            stderr += "\n[saída excedeu o limite de 100.000 caracteres desta chamada; solicite apenas o trecho necessário ou divida a leitura em partes]"
        if stream_error:
            return {
                "ok": False, "error": stream_error, "stdout": stdout, "stderr": stderr,
                "exit_code": exit_code, "workspace": "/home/ada-runner/workspace",
                "timeout_seconds": timeout_seconds, "executor": "VPS",
            }
        if exit_code is None:
            return {
                "ok": False,
                "error": "A conexão de streaming terminou sem confirmação do código de saída. Verifique o estado antes de repetir ações.",
                "stdout": stdout, "stderr": stderr,
                "workspace": "/home/ada-runner/workspace",
                "timeout_seconds": timeout_seconds, "executor": "VPS",
            }
        return {
            "ok": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "workspace": "/home/ada-runner/workspace",
            "timeout_seconds": timeout_seconds,
            "executor": "VPS",
            "session_note": "Terminal conectado ao VPS; arquivos ficam no workspace persistente do servidor.",
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": "O streaming da VPS excedeu o limite de espera. Confira se ada-executor está ativo."}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"O executor VPS respondeu com HTTP {exc.response.status_code}."}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"ok": False, "error": f"Não foi possível comunicar com o executor VPS ({type(exc).__name__})."}


async def _request_vps_admin_install_tools() -> dict[str, Any]:
    """Request the fixed, root-owned installation job; never accepts package names."""
    settings = _vps_settings()
    if settings is None:
        return {
            "ok": False,
            "error": "A instalação administrativa exige ADA_EXECUTOR_URL e ADA_EXECUTOR_TOKEN configurados para a VPS.",
        }
    base_url, headers = settings
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.post(
                f"{base_url}/admin/install-tools",
                headers=headers,
                json={},
            )
        if response.status_code in (401, 403):
            return {
                "ok": False,
                "error": f"O executor da VPS recusou o token (HTTP {response.status_code}). Confira /opt/ada-executor/.token.",
            }
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "started":
            return {
                "ok": False,
                "error": "O executor não confirmou o início da tarefa administrativa.",
            }
        return {
            "ok": True,
            "status": "started",
            "executor": "VPS administrativo controlado",
            "message": str(payload.get("message") or "Solicitação de instalação aceita."),
            "completion_confirmed": False,
            "note": "A tarefa foi iniciada em segundo plano. Isso ainda não confirma que a instalação terminou.",
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": "Tempo esgotado ao solicitar a instalação administrativa na VPS."}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"A rota administrativa respondeu com HTTP {exc.response.status_code}."}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"ok": False, "error": f"Falha ao solicitar a instalação administrativa ({type(exc).__name__})."}


async def _request_vps_admin_readonly(path: str, operation: str) -> dict[str, Any]:
    """Read-only administrative diagnostics; operations and paths are fixed by the caller."""
    settings = _vps_settings()
    if settings is None:
        return {
            "ok": False,
            "error": "A operação administrativa exige ADA_EXECUTOR_URL e ADA_EXECUTOR_TOKEN no /opt/ada-m/.env.",
        }
    base_url, headers = settings
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.get(f"{base_url}{path}", headers=headers)
        if response.status_code in (401, 403):
            return {
                "ok": False,
                "error": f"O executor da VPS recusou o token (HTTP {response.status_code}). Confira /opt/ada-executor/.token.",
            }
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            return {"ok": False, "error": "O executor não confirmou a operação administrativa."}
        output = str(payload.get("output") or "")[:10000]
        return {
            "ok": True,
            "exit_code": 0,
            "stdout": output,
            "stderr": "",
            "workspace": "/opt/ada-executor",
            "executor": "VPS administrativo somente leitura",
            "operation": operation,
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": f"Tempo esgotado ao consultar {operation} na VPS."}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"A rota administrativa respondeu com HTTP {exc.response.status_code}."}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"ok": False, "error": f"Falha ao consultar {operation} ({type(exc).__name__})."}


async def _request_vps_admin_diagnostics() -> dict[str, Any]:
    return await _request_vps_admin_readonly("/admin/diagnostics", "diagnostics")


async def _request_vps_admin_install_tools_status() -> dict[str, Any]:
    return await _request_vps_admin_readonly(
        "/admin/install-tools/status", "install-tools-status"
    )

async def run_terminal_command(session: dict[str, Any], command: Any, on_event=None) -> dict[str, Any]:
    """Execute commands exclusively on the private VPS executor."""
    try:
        clean_command = validate_command(command)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    # These exact virtual commands map to fixed, root-owned systemd jobs.
    # Arbitrary arguments are never accepted by the administrative API.
    if clean_command == "ada-admin install-tools":
        return await _request_vps_admin_install_tools()
    if clean_command == "ada-admin diagnostics":
        return await _request_vps_admin_diagnostics()
    if clean_command == "ada-admin install-tools-status":
        return await _request_vps_admin_install_tools_status()
    if clean_command.startswith("ada-admin"):
        return {
            "ok": False,
            "error": (
                "Operação administrativa não autorizada. Comandos virtuais disponíveis: "
                "'ada-admin diagnostics', 'ada-admin install-tools-status' e "
                "'ada-admin install-tools'."
            ),
        }
    if not is_terminal_configured():
        return {
            "ok": False,
            "error": (
                "Terminal da VPS não configurado. Defina ADA_EXECUTOR_URL=http://127.0.0.1:8000 "
                "e ADA_EXECUTOR_TOKEN no arquivo /opt/ada-m/.env."
            ),
        }
    return await _run_on_vps(clean_command, on_event=on_event)
