from __future__ import annotations
import base64, binascii, io, os, time
from collections import defaultdict, deque
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

router = APIRouter()
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
IMAGE_MODEL = os.getenv("IMAGE_GENERATION_MODEL", "@cf/black-forest-labs/flux-1-schnell").strip()
IMAGE_EDIT_MODEL = os.getenv("IMAGE_EDIT_MODEL", "@cf/black-forest-labs/flux-2-klein-9b").strip()
RATE_LIMIT: dict[str, deque[float]] = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_LIMIT_REQUESTS = 3
MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024 * 1024
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
class ImageEditRequest(BaseModel):
 image_data: str = Field(min_length=1, max_length=7_000_000)
 mime_type: str = Field(pattern="^(image/jpeg|image/png|image/webp)$")
 prompt: str = Field(min_length=3, max_length=1800)
class ImageGenerationResponse(BaseModel):
 image_data: str
 mime_type: str = "image/png"
 model: str

def check_rate_limit(request: Request) -> None:
 ip = request.client.host if request.client else "unknown"
 now = time.monotonic()
 recent = RATE_LIMIT[ip]
 while recent and now - recent[0] > RATE_WINDOW_SECONDS: recent.popleft()
 if len(recent) >= RATE_LIMIT_REQUESTS:
  raise HTTPException(status_code=429, detail="Limite temporário: aguarde um minuto antes de gerar ou editar outra imagem.")
 recent.append(now)

def cloudflare_url(model: str) -> str:
 return f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"

def decode_image_result(response: httpx.Response, model: str) -> ImageGenerationResponse:
 content_type = response.headers.get("content-type", "").lower()
 if content_type.startswith("image/"):
  image_bytes, mime_type = response.content, content_type.split(";")[0]
 else:
  try: body = response.json()
  except ValueError: raise HTTPException(status_code=502, detail="A Cloudflare retornou uma resposta de imagem inválida.")
  result = body.get("result") if isinstance(body, dict) else None
  encoded = result.get("image") if isinstance(result, dict) else None
  if not isinstance(encoded, str) or not encoded:
   errors = body.get("errors", []) if isinstance(body, dict) else []
   detail = str(errors[0].get("message", "")) if errors and isinstance(errors[0], dict) else ""
   raise HTTPException(status_code=502, detail=detail[:220] or "A Cloudflare não retornou a imagem.")
  try: image_bytes = base64.b64decode(encoded, validate=True)
  except (binascii.Error, ValueError): raise HTTPException(status_code=502, detail="A imagem retornada pela Cloudflare está corrompida.")
  mime_type = "image/png"
 if not image_bytes or len(image_bytes) > MAX_OUTPUT_BYTES:
  raise HTTPException(status_code=502, detail="A imagem retornada está vazia ou excede o limite permitido.")
 return ImageGenerationResponse(image_data=base64.b64encode(image_bytes).decode("ascii"), mime_type=mime_type, model=model)

def cloudflare_error(response: httpx.Response) -> None:
 if response.status_code in (401, 403):
  raise HTTPException(status_code=502, detail="A Cloudflare recusou a chave. Confira o token e as permissões Workers AI.")
 if response.status_code == 429:
  raise HTTPException(status_code=429, detail="Limite diário ou temporário da Cloudflare atingido. Tente novamente mais tarde.")
 if response.status_code >= 400:
  try:
   errors = response.json().get("errors", [])
   message = errors[0].get("message", "") if errors else ""
  except (ValueError, AttributeError, TypeError): message = ""
  raise HTTPException(status_code=502, detail=str(message)[:220] or f"Falha no serviço de imagens (HTTP {response.status_code}).")

@router.get("/api/image-generation/status")
async def image_generation_status() -> dict[str, object]:
 return {"configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN), "provider": "Cloudflare Workers AI", "model": IMAGE_MODEL, "image_edit_model": IMAGE_EDIT_MODEL, "image_edit_supported": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN)}

@router.post("/api/generate-image", response_model=ImageGenerationResponse)
async def generate_image(payload: ImageGenerationRequest, request: Request) -> ImageGenerationResponse:
 if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
  raise HTTPException(status_code=503, detail="Criação de imagens ainda não configurada. Adicione CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN nas variáveis do Render.")
 check_rate_limit(request)
 prompt = f"{payload.prompt.strip()}. {STYLE_SUFFIXES[payload.style]}"[:2048]
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(150.0, connect=10.0)) as client:
   response = await client.post(cloudflare_url(IMAGE_MODEL), headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}, json={"prompt": prompt, "steps": 4})
  cloudflare_error(response)
  return decode_image_result(response, IMAGE_MODEL)
 except HTTPException: raise
 except httpx.TimeoutException: raise HTTPException(status_code=504, detail="A geração demorou demais. Tente novamente com uma descrição mais simples.")
 except httpx.HTTPError as exc:
  print(f"Image generation network error ({type(exc).__name__})")
  raise HTTPException(status_code=502, detail="Não foi possível conectar ao serviço de criação de imagens.")

@router.post("/api/edit-image", response_model=ImageGenerationResponse)
async def edit_image(payload: ImageEditRequest, request: Request) -> ImageGenerationResponse:
 if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
  raise HTTPException(status_code=503, detail="Edição de imagens não configurada. Confira CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN no Render.")
 check_rate_limit(request)
 try: raw = base64.b64decode(payload.image_data, validate=True)
 except (binascii.Error, ValueError): raise HTTPException(status_code=400, detail="A imagem enviada é inválida.")
 if not raw or len(raw) > MAX_INPUT_BYTES: raise HTTPException(status_code=413, detail="A foto deve ter até 5 MB.")
 try:
  with Image.open(io.BytesIO(raw)) as source:
   source.load()
   source.thumbnail((511, 511), Image.Resampling.LANCZOS)
   prepared = io.BytesIO()
   source.convert("RGB").save(prepared, format="JPEG", quality=88, optimize=True)
   image_bytes = prepared.getvalue()
 except (UnidentifiedImageError, OSError, ValueError):
  raise HTTPException(status_code=400, detail="Não foi possível processar essa foto. Envie JPG, PNG ou WebP.")
 prompt = (
  "Create a new transformed image using input_image_0 as the reference photo. "
  "Apply the requested visual style clearly; do not reproduce the original image unchanged. "
  "Preserve the subject's recognizable facial features and hairstyle while redrawing the subject in the requested style. "
  + payload.prompt.strip()
  + ". The result must visibly reflect the requested transformation."
 )
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
   response = await client.post(cloudflare_url(IMAGE_EDIT_MODEL), headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}, data={"prompt": prompt[:2200], "width": "1024", "height": "1024", "guidance": "4"}, files={"input_image_0": ("reference.jpg", image_bytes, "image/jpeg")})
  cloudflare_error(response)
  return decode_image_result(response, IMAGE_EDIT_MODEL)
 except HTTPException: raise
 except httpx.TimeoutException: raise HTTPException(status_code=504, detail="A edição demorou demais. Tente novamente com uma foto menor ou outro pedido.")
 except httpx.HTTPError as exc:
  print(f"Image editing network error ({type(exc).__name__})")
  raise HTTPException(status_code=502, detail="Não foi possível conectar ao serviço de edição de imagens.")
