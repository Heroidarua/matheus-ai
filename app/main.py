from __future__ import annotations

import ast
import os
import operator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "http://localhost:11434/v1").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()

app = FastAPI(title="Matheus AI", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ChatResponse(BaseModel):
    reply: str
    model: str


def require_app_key(x_app_key: str | None = Header(default=None)) -> None:
    if APP_API_KEY and x_app_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Chave da aplicação inválida.")


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "Matheus AI"}


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_calculate(expression: str) -> int | float:
    if len(expression) > 120:
        raise ValueError("Expressão muito longa.")
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Expoente muito alto.")
            result = _ALLOWED_BINOPS[type(node.op)](left, right)
            if abs(result) > 1e100:
                raise ValueError("Resultado muito grande.")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](visit(node.operand))
        raise ValueError("A expressão contém operações não permitidas.")

    return visit(tree)


def local_tool(message: str) -> str | None:
    lowered = message.strip().lower()
    if lowered.startswith("/hora") or lowered in {"que horas são?", "qual é a hora atual?"}:
        return "Horário atual em UTC: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if lowered.startswith("/calc "):
        expression = message.strip()[6:].strip()
        try:
            return f"Resultado: {safe_calculate(expression)}"
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as exc:
            return f"Não consegui calcular: {exc}"
    return None


SYSTEM_PROMPT = """Você é Matheus AI, um assistente pessoal em português do Brasil.
Ajude com programação, Linux, Termux, automação, pesquisa, aprendizado, escrita e projetos pessoais.
Seja prático, direto, preciso e honesto. Quando necessário, explique passo a passo e priorize soluções compatíveis com Android, Termux, Linux e dispositivos com poucos recursos.
Não afirme ter executado ações que não executou. Se não souber ou não puder verificar algo, diga claramente.
Não peça segredos ou credenciais. Não alegue acesso ao sistema local do usuário.
Comandos úteis da interface: /calc EXPRESSÃO e /hora.
"""


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(require_app_key)])
async def chat(request: ChatRequest) -> ChatResponse:
    last_user_message = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    if not last_user_message:
        raise HTTPException(status_code=400, detail="Envie ao menos uma mensagem do usuário.")

    tool_result = local_tool(last_user_message)
    if tool_result is not None:
        return ChatResponse(reply=tool_result, model="ferramenta-local")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": m.role, "content": m.content} for m in request.messages)

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.6,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            response = await client.post(
                f"{MODEL_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("Resposta vazia do modelo")
        return ChatResponse(reply=reply.strip(), model=str(data.get("model", MODEL_NAME)))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="O modelo demorou demais para responder.")
    except httpx.HTTPStatusError as exc:
        detail = "O provedor do modelo retornou um erro."
        try:
            detail = exc.response.json().get("error", {}).get("message", detail)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=detail[:500])
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="Não foi possível obter uma resposta válida do modelo. Confira MODEL_BASE_URL, MODEL_NAME e a chave configurada.",
        )
