from __future__ import annotations

import base64
import binascii
import os
import time
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
IMAGE_MODEL = os.getenv("IMAGE_GENERATION_MODEL", "@cf/black-forest-labs/flux-1-schnell").strip()
RATE_LIMIT: dict[str, deque[float]] = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_LIMIT_REQUESTS = 3

STYLE_SUFFIXES = {
    "realista": "Photorealistic, natural lighting, detailed textures, professional photography.",
    "anime": "High-quality anime illustration, expressive details, polished Japanese animation aesthetic.",
    "3d": "High-quality 3D render, detailed materials, cinematic lighting, polished composition.",
    "ilustracao": "Beautiful digital illustration, refined linework, rich colors, professional concept art.",
    "minimalista": "Minimalist visual design, clean composition, balanced negative space, elegant details.",
}

class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1800)
    style: str = Field(default="realista", pattern="^(realista|anime|3d|ilustracao|minimalista)$")

class ImageGenerationResponse(BaseModel):
    image_data: str
    mime_type: str = "image/png"
    model: str

@router.get("/api/image-generation/status")
async def image_generation_status() -> dict[str, object]:
    return {
        "configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN),
        "provider": "Cloudflare Workers AI",
        "model": IMAGE_MODEL,
    }

@router.post("/api/generate-image", response_model=ImageGenerationResponse)
async def generate_image(payload: ImageGenerationRequest, request: Request) -> ImageGenerationResponse:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Criação de imagens ainda não configurada. Adicione CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN nas variáveis do Render.",
        )

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = RATE_LIMIT[client_ip]
    while recent and now - recent[0] > RATE_WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Limite temporário: aguarde um minuto antes de gerar outra imagem.")
    recent.append(now)

    prompt = payload.prompt.strip()
    prompt = f"{prompt}. {STYLE_SUFFIXES[payload.style]}"
    if len(prompt) > 2048:
        prompt = prompt[:2048]

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{IMAGE_MODEL}"
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(150.0, connect=10.0)) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"prompt": prompt, "steps": 4},
            )
        if response.status_code == 401 or response.status_code == 403:
            raise HTTPException(status_code=502, detail="A Cloudflare recusou a chave. Confira o token e as permissões Workers AI.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Limite diário ou temporário da Cloudflare atingido. Tente novamente mais tarde.")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Falha no serviço de imagens (HTTP {response.status_code}).")

        content_type = response.headers.get("content-type", "").lower()
        if content_type.startswith("image/"):
            image_bytes = response.content
            mime_type = content_type.split(";")[0]
        else:
            try:
                body = response.json()
            except ValueError:
                raise HTTPException(status_code=502, detail="A Cloudflare retornou uma resposta de imagem inválida.")
            result = body.get("result") if isinstance(body, dict) else None
            encoded = result.get("image") if isinstance(result, dict) else result
            if not isinstance(encoded, str) or not encoded:
                errors = body.get("errors", []) if isinstance(body, dict) else []
                detail = str(errors[0].get("message", "")) if errors and isinstance(errors[0], dict) else ""
                raise HTTPException(status_code=502, detail=detail[:220] or "A Cloudflare não retornou a imagem.")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise HTTPException(status_code=502, detail="A imagem retornada pela Cloudflare está corrompida.")
            mime_type = "image/png"

        if not image_bytes or len(image_bytes) > 12 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="A imagem gerada está vazia ou excede o limite permitido.")
        return ImageGenerationResponse(
            image_data=base64.b64encode(image_bytes).decode("ascii"),
            mime_type=mime_type,
            model=IMAGE_MODEL,
        )
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="A geração demorou demais. Tente novamente com uma descrição mais simples.")
    except httpx.HTTPError as exc:
        print(f"Image generation network error ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível conectar ao serviço de criação de imagens.")
