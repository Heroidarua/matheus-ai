from __future__ import annotations

import ast
import ipaddress
import asyncio
import csv
import json
import base64
import binascii
import operator
import os
import re
import secrets
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from livekit import api as livekit_api

from app.research_engine import build_search_query, classify_research_topic, is_relevant_result, rank_results
from app.google_search import google_grounded_search
from app.google_workspace import router as google_workspace_router
from app.file_library import router as file_library_router, search_library
from app.image_generation import router as image_generation_router
from app.companion import (
    build_companion_prompt,
    companion_storage_status,
    get_companion_state,
    update_companion_state,
)
from app.long_term_memory import (
    forget_all as forget_long_term_memory,
    list_memories as list_long_term_memories,
    remember as remember_long_term_memory,
    retrieve as retrieve_long_term_memory,
    storage_status as long_term_memory_storage_status,
)

load_dotenv()

TTS_API_URL = os.getenv("TTS_API_URL", "").strip().rstrip("/")
TTS_API_KEY = os.getenv("TTS_API_KEY", "").strip()
TTS_VOICE = os.getenv("TTS_VOICE", "pf_dora").strip() or "pf_dora"

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "http://localhost:11434/v1").rstrip("/")
# Padrão: Gemma 4. O LOCAL.md recomenda qwen2.5:3b para rodar em casa;
# defina MODEL_NAME no ambiente para usar outro modelo.
MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:31b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", str(ROOT / "data" / "knowledge")))
MAX_KNOWLEDGE_FILE_BYTES = 1_000_000
MAX_KNOWLEDGE_FILES = 100
MAX_RETRIEVED_CHUNKS = 4
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").strip().rstrip("/")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "ada-m-voice").strip() or "ada-m-voice"
LIVEKIT_TOKEN_TTL_SECONDS = 600
LIVEKIT_TOKEN_ISSUES: dict[str, float] = {}
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
IMAGE_EDIT_MODEL = os.getenv("IMAGE_EDIT_MODEL", "Qwen/Qwen-Image-Edit")
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_FILE_CHARS = 40000
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
APP_STARTED_AT = time.time()
DIAGNOSTICS = {"requests": 0, "successes": 0, "errors": 0, "searches": 0, "search_successes": 0, "last_error": None, "last_search_provider": None}

app = FastAPI(title="ADA-M", version="0.3.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("GITHUB_SESSION_SECRET") or secrets.token_urlsafe(48),
    session_cookie="matheus_ai_session",
    same_site="lax",
    https_only=os.getenv("COOKIE_HTTPS_ONLY", "true").lower() == "true",
    max_age=60 * 60 * 24 * 14,
)
class VersionedStaticFiles(StaticFiles):
    """Serve estáticos com Cache-Control: assets versionados (?v=...) são imutáveis."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        query = scope.get("query_string", b"").decode()
        if "v=" in query:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
        return response


app.mount("/static", VersionedStaticFiles(directory=str(STATIC_DIR)), name="static")
from app.github_integration import router as github_router
app.include_router(github_router)
app.include_router(google_workspace_router)
app.include_router(file_library_router)
app.include_router(image_generation_router)


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str | list[dict[str, Any]]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    mode: str = Field(default="normal", pattern="^(normal|livre|programador|estudo|criativo)$")
    response_length: str = Field(default="detalhada", pattern="^(curta|normal|detalhada)$")
    web_search: bool = False
    stream: bool = False
    memory: list[str] = Field(default_factory=list, max_length=30)


class ChatResponse(BaseModel):
    reply: str
    model: str
    sources: list[dict[str, str]] = Field(default_factory=list)


class ImageEditRequest(BaseModel):
    image_data: str = Field(min_length=1)
    mime_type: str = Field(pattern="^(image/jpeg|image/png|image/webp)$")
    prompt: str = Field(min_length=3, max_length=2000)

class TTSProxyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    speed: float = Field(default=1.0, ge=0.7, le=1.3)


class ImageEditResponse(BaseModel):
    image_data: str
    mime_type: str = "image/png"
    model: str


def require_app_key(x_app_key: str | None = Header(default=None)) -> None:
    if APP_API_KEY and x_app_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Chave da aplicação inválida.")


@app.post("/api/livekit/token", status_code=201)
async def create_livekit_token(request: Request) -> dict[str, Any]:
    """Emite token LiveKit curto, limitado a áudio e a uma sala da sessão ADA-M."""
    if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        raise HTTPException(status_code=503, detail="O modo LiveKit ainda não está configurado no servidor.")

    origin = request.headers.get("origin") or request.headers.get("referer")
    request_host = request.headers.get("host", "").lower()
    origin_host = urlparse(origin).netloc.lower() if origin else ""
    if not origin_host or not request_host or origin_host != request_host:
        raise HTTPException(status_code=403, detail="Origem não autorizada.")

    session_id = request.session.get("companion_id")
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        request.session["companion_id"] = session_id

    now = time.time()
    last_issued = LIVEKIT_TOKEN_ISSUES.get(session_id, 0)
    if now - last_issued < 5:
        raise HTTPException(status_code=429, detail="Aguarde alguns segundos antes de solicitar outro token.")
    LIVEKIT_TOKEN_ISSUES[session_id] = now
    if len(LIVEKIT_TOKEN_ISSUES) > 5000:
        cutoff = now - 3600
        for key, issued_at in list(LIVEKIT_TOKEN_ISSUES.items()):
            if issued_at < cutoff:
                LIVEKIT_TOKEN_ISSUES.pop(key, None)

    # Uma sala nova por sessão de voz garante que o dispatch do agente ocorra
    # mesmo quando o usuário encerra e inicia uma nova chamada rapidamente.
    room_name = "ada-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:22].lower()

    identity = "user-" + secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16].lower()
    try:
        token = (
            livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name("Usuário ADA-M")
            .with_grants(livekit_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_publish_sources=["microphone"],
                can_subscribe=True,
                can_publish_data=False,
            ))
            .with_ttl(timedelta(seconds=LIVEKIT_TOKEN_TTL_SECONDS))
            .with_room_config(livekit_api.RoomConfiguration(
                agents=[livekit_api.RoomAgentDispatch(agent_name=LIVEKIT_AGENT_NAME)]
            ))
        )
        participant_token = token.to_jwt()
    except Exception as exc:
        print(f"LiveKit token generation failed ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="Não foi possível preparar a conexão de voz agora.")

    return {
        "server_url": LIVEKIT_URL,
        "participant_token": participant_token,
        "room_name": room_name,
        "participant_identity": identity,
        "expires_in": LIVEKIT_TOKEN_TTL_SECONDS,
    }


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/")
async def home() -> FileResponse:
    # O HTML sempre revalida (ETag); o cache longo vale só para assets versionados.
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "ADA-M"}


@app.get("/api/tts/status", dependencies=[Depends(require_app_key)])
async def tts_status() -> dict[str, Any]:
    """Informa se a síntese feminina remota está configurada, sem revelar segredos."""
    return {
        "configured": bool(TTS_API_URL),
        "engine": "Kokoro-82M" if TTS_API_URL else "browser-fallback",
        "voice": TTS_VOICE if TTS_API_URL else None,
        "language": "pt-BR",
    }


@app.post("/api/tts/speech", dependencies=[Depends(require_app_key)])
async def tts_speech(data: TTSProxyRequest) -> Response:
    """Proxy seguro para o TTS: a chave do serviço nunca chega ao navegador."""
    if not TTS_API_URL:
        raise HTTPException(status_code=503, detail="Voz natural ainda não configurada; usando a voz do navegador.")
    headers = {"Authorization": f"Bearer {TTS_API_KEY}"} if TTS_API_KEY else {}
    payload = {
        "model": "kokoro",
        "input": data.text.strip(),
        "voice": TTS_VOICE,
        "response_format": "wav",
        "speed": data.speed,
    }
    if not payload["input"]:
        raise HTTPException(status_code=400, detail="Texto vazio.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=8.0)) as client:
            upstream = await client.post(
                f"{TTS_API_URL}/v1/audio/speech",
                headers=headers,
                json=payload,
            )
        upstream.raise_for_status()
        content_type = upstream.headers.get("content-type", "audio/wav").split(";")[0].strip()
        if not content_type.startswith("audio/") or not upstream.content:
            raise HTTPException(status_code=502, detail="O serviço de voz retornou um áudio inválido.")
        return Response(
            content=upstream.content,
            media_type=content_type,
            headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="ada-m.wav"'},
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="A síntese de voz demorou demais. Tente novamente.")
    except httpx.HTTPStatusError as exc:
        print(f"TTS provider HTTP {exc.response.status_code}")
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="A autenticação do serviço de voz falhou. Confira TTS_API_KEY.")
        if exc.response.status_code == 503:
            raise HTTPException(status_code=503, detail="O serviço de voz ainda está carregando.")
        raise HTTPException(status_code=502, detail="O serviço de voz não conseguiu gerar o áudio.")
    except httpx.HTTPError as exc:
        print(f"TTS provider connection error ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível conectar ao serviço de voz.")


@app.get("/api/companion/state", dependencies=[Depends(require_app_key)])
async def companion_state_endpoint(http_request: Request) -> dict[str, Any]:
    """Estado afetivo simulado desta sessão; não expõe mensagens ou conteúdo privado."""
    session_id = http_request.session.get("companion_id")
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        http_request.session["companion_id"] = session_id
    state = await asyncio.to_thread(get_companion_state, session_id)
    return {
        "identity": "ADA-M / Matheus AI",
        "state": state,
        "storage": companion_storage_status(),
        "note": "Estados afetivos simulados, não sentimentos subjetivos.",
    }

@app.get("/api/memory", dependencies=[Depends(require_app_key)])
async def get_long_term_memory(http_request: Request) -> dict[str, Any]:
    owner_id = http_request.session.get("companion_id")
    if not owner_id:
        owner_id = secrets.token_urlsafe(32)
        http_request.session["companion_id"] = owner_id
    items = await asyncio.to_thread(list_long_term_memories, owner_id)
    return {"items": items, "count": len(items), "storage": long_term_memory_storage_status()}


@app.delete("/api/memory", dependencies=[Depends(require_app_key)])
async def delete_long_term_memory(http_request: Request) -> dict[str, Any]:
    owner_id = http_request.session.get("companion_id")
    if not owner_id:
        return {"deleted": 0}
    count = await asyncio.to_thread(forget_long_term_memory, owner_id)
    return {"deleted": count}


@app.get("/api/diagnostics", dependencies=[Depends(require_app_key)])
async def diagnostics() -> dict[str, Any]:
    """Diagnóstico operacional sem revelar chaves, URLs privadas ou conteúdo do usuário."""
    provider_configured = bool(MODEL_BASE_URL and MODEL_NAME and OPENAI_API_KEY)
    probe = {"status": "não verificado", "latency_ms": None}
    if provider_configured:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
                response = await client.get(
                    f"{MODEL_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                )
            probe["latency_ms"] = round((time.perf_counter() - started) * 1000)
            probe["status"] = "disponível" if response.is_success else f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            probe["latency_ms"] = round((time.perf_counter() - started) * 1000)
            probe["status"] = "tempo esgotado"
        except httpx.HTTPError:
            probe["latency_ms"] = round((time.perf_counter() - started) * 1000)
            probe["status"] = "falha de conexão"
    search_providers = {
        "Google Grounding": bool(os.getenv("GOOGLE_GEMINI_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()),
        "Brave": bool(os.getenv("BRAVE_SEARCH_API_KEY", "").strip()),
        "SearXNG": bool(os.getenv("SEARXNG_URL", "").strip()),
        "Buscadores públicos de fallback": True,
    }
    return {
        "app": "operacional",
        "uptime_seconds": round(time.time() - APP_STARTED_AT),
        "model": {"configured": provider_configured, **probe},
        "voice": {
            "configured": bool(TTS_API_URL),
            "engine": "Kokoro-82M" if TTS_API_URL else "voz do navegador",
            "voice": TTS_VOICE if TTS_API_URL else None,
        },
        "companion_storage": companion_storage_status(),
        "long_term_memory": long_term_memory_storage_status(),
        "search": {"providers": search_providers, "last_provider": DIAGNOSTICS["last_search_provider"]},
        "metrics": {key: DIAGNOSTICS[key] for key in ("requests", "successes", "errors", "searches", "search_successes")},
        "last_error": DIAGNOSTICS["last_error"],
        "note": "Métricas em memória deste processo; podem reiniciar após novo deploy ou reinicialização.",
    }


@app.post("/api/edit-image", response_model=ImageEditResponse, dependencies=[Depends(require_app_key)])
async def edit_image(request: ImageEditRequest) -> ImageEditResponse:
    if not HF_TOKEN:
        raise HTTPException(status_code=503, detail="A edição de imagens ainda não está configurada. Adicione HF_TOKEN nas variáveis do Render.")

    try:
        raw = base64.b64decode(request.image_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="A imagem enviada é inválida.")
    if not raw or len(raw) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="A imagem deve ter até 5 MB.")

    try:
        from huggingface_hub import InferenceClient

        def run_edit() -> bytes:
            client = InferenceClient(provider="fal-ai", api_key=HF_TOKEN, timeout=180)
            edited = client.image_to_image(raw, prompt=request.prompt.strip(), model=IMAGE_EDIT_MODEL)
            output = BytesIO()
            edited.save(output, format="PNG")
            return output.getvalue()

        output_bytes = await asyncio.to_thread(run_edit)
        return ImageEditResponse(
            image_data=base64.b64encode(output_bytes).decode("ascii"),
            mime_type="image/png",
            model=IMAGE_EDIT_MODEL,
        )
    except Exception as exc:
        print(f"Image editing provider error ({type(exc).__name__}): {str(exc)[:300]}")
        raise HTTPException(status_code=502, detail="O serviço de edição de imagens falhou. Confira HF_TOKEN, o acesso ao provedor e os créditos disponíveis.")


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
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


def content_as_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        str(part.get("text", ""))
        for part in content
        if part.get("type") == "text"
    ).strip()


def requires_live_search(message: str) -> bool:
    """Detecta perguntas factuais atuais que devem pesquisar mesmo se o toggle estiver desligado."""
    text = re.sub(r"\s+", " ", message.casefold()).strip()
    current_topic_patterns = (
        r"\bele[ií]ç(?:ão|ões)\b", r"\bresultado(?:s)?\b.*\b(ele[ií]ç|vota|jogo|partida)",
        r"\bquem (?:ganhou|venceu|é o vencedor|foi eleito)\b", r"\bquem (?:é|foi) (?!você\b|voce\b|eu\b|ele\b|ela\b|isso\b|isto\b)[\wÀ-ÿ][\wÀ-ÿ .'-]{1,80}", r"\bapuraç(?:ão|ões)\b",
        r"\bnot[ií]cias?\b", r"\b(?:hoje|ontem|agora|atualmente|neste momento|últim[oa]s?)\b",
        r"\baconteceu\b", r"\bquem (?:é|está como) (?:o|a) (?:atual|presidente|governador|prefeito)\b
