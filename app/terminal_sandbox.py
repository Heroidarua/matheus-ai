"""Terminal execution for ADA-M through its private VPS executor.

When ADA_EXECUTOR_URL is configured, commands run on the user's VPS through
Cloudflare Access and the executor's own bearer token. Render Sandboxes remain
available as a backward-compatible fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
from typing import Any

import httpx

MAX_COMMAND_CHARS = 4000
MAX_OUTPUT_CHARS = 100000
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


async def _run_on_vps(command: str, on_event=None) -> dict[str, Any]:
    """Stream command output from the VPS executor while preserving bounded output."""
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
                            f"O Cloudflare/VPS recusou a autenticação (HTTP {response.status_code}). "
                            "Confira o Service Token do Cloudflare Access e ADA_EXECUTOR_TOKEN no Render."
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
            "error": "A instalação administrativa exige o executor VPS e as três credenciais de autenticação configuradas.",
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
                "error": f"Cloudflare Access ou executor recusou a autenticação (HTTP {response.status_code}).",
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
            "error": "A operação administrativa exige ADA_EXECUTOR_URL e as três credenciais de autenticação no Render.",
        }
    base_url, headers = settings
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = await client.get(f"{base_url}{path}", headers=headers)
        if response.status_code in (401, 403):
            return {
                "ok": False,
                "error": f"Cloudflare Access ou executor recusou a autenticação (HTTP {response.status_code}).",
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

def _network_policy():
    """Allow unrestricted outbound network access for the Render terminal sandbox."""
    return "allow-all"


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
    output_truncated = False
    async for event in client.sandboxes.exec(sandbox_id, wrapped):
        if isinstance(event, SandboxExecOutput):
            chunk = str(event.data or "")
            remaining = max(0, MAX_OUTPUT_CHARS - collected)
            if len(chunk) > remaining:
                output_truncated = True
            if remaining:
                clipped = chunk[:remaining]
                (stderr if event.stream == "stderr" else stdout).append(clipped)
                collected += len(clipped)
        elif isinstance(event, SandboxExecExit):
            exit_code = int(event.exit_code)
    if exit_code is None:
        return {"ok": False, "error": "A execução terminou sem um código de saída confirmado.", "stdout": "".join(stdout), "stderr": "".join(stderr)}
    out, err = "".join(stdout), "".join(stderr)
    if output_truncated:
        err += "\n[saída excedeu o limite de 100.000 caracteres desta chamada; solicite apenas o trecho necessário ou divida a leitura em partes]"
    return {"ok": exit_code == 0, "exit_code": exit_code, "stdout": out, "stderr": err, "workspace": WORKSPACE, "timeout_seconds": COMMAND_TIMEOUT_SECONDS}


async def run_terminal_command(session: dict[str, Any], command: Any, on_event=None) -> dict[str, Any]:
    """Execute on the VPS when configured; otherwise preserve Render sandbox."""
    try:
        clean_command = validate_command(command)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    # This exact virtual command maps to one fixed root-owned systemd job.
    # No package names, shell fragments, or arbitrary arguments reach the admin API.
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
    if os.getenv("ADA_EXECUTOR_URL", "").strip():
        return await _run_on_vps(clean_command, on_event=on_event)
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
