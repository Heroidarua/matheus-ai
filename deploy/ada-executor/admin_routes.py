"""Authenticated, fixed-operation routes for the standalone ADA-M VPS executor."""
from __future__ import annotations

import asyncio
from typing import Callable

from fastapi import APIRouter, Header, HTTPException

ADMIN_SCRIPT = "/usr/local/sbin/ada-admin"


def create_admin_router(token_validator: Callable[[str | None], bool]) -> APIRouter:
    """Build routes that expose only curated, read-only administrative operations."""

    router = APIRouter()

    async def run_admin(operation: str) -> dict[str, str | bool]:
        # The operation is selected only by a route below; no user-supplied shell
        # text, package name, service name, or extra argument reaches sudo.
        try:
            process = await asyncio.create_subprocess_exec(
                "sudo", "-n", ADMIN_SCRIPT, operation,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Tempo limite administrativo excedido") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Falha ao consultar a administração da VPS") from exc

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[:800]
            raise HTTPException(status_code=500, detail=detail or "Operação administrativa falhou")
        return {
            "ok": True,
            "operation": operation,
            "output": stdout.decode("utf-8", errors="replace")[:10000],
        }

    def authorize(authorization: str | None) -> None:
        if not token_validator(authorization):
            raise HTTPException(status_code=401, detail="Não autorizado")

    @router.get("/admin/diagnostics")
    async def admin_diagnostics(authorization: str | None = Header(default=None)):
        authorize(authorization)
        return await run_admin("diagnostics")

    @router.get("/admin/install-tools/status")
    async def admin_install_tools_status(authorization: str | None = Header(default=None)):
        authorize(authorization)
        return await run_admin("install-tools-status")

    return router
