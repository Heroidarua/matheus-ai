"""Google Search Grounding adapter using Gemini generateContent.

Gemini is used only as a live web-research tool; ADA-M's configured chat model
continues to generate the final answer.
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_MODEL = "gemini-2.5-flash"
GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.casefold().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        return True
    except (TypeError, ValueError):
        return False


def _extract_grounded_output(payload: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Parse Gemini text and Google Search grounding metadata."""
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return "", []

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    summary = "\n".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()

    metadata = candidate.get("groundingMetadata") or {}
    chunks = metadata.get("groundingChunks") or []
    supports = metadata.get("groundingSupports") or []
    citations: list[dict[str, str]] = []
    for chunk_index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web") or {}
        url = str(web.get("uri", "")).strip()
        title = str(web.get("title", "")).strip()
        if not _public_http_url(url):
            continue
        excerpt = ""
        for support in supports:
            if not isinstance(support, dict):
                continue
            if chunk_index in (support.get("groundingChunkIndices") or []):
                segment = support.get("segment") or {}
                excerpt = str(segment.get("text", "")).strip()
                if excerpt:
                    break
        item = {
            "title": (title or url)[:200],
            "url": url[:2000],
            "snippet": re.sub(r"\s+", " ", excerpt or summary).strip()[:500],
        }
        if not any(existing["url"] == item["url"] for existing in citations):
            citations.append(item)
        if len(citations) >= 6:
            break
    return re.sub(r"\n{3,}", "\n\n", summary)[:6000], citations


async def google_grounded_search(
    query: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Search the live web using Gemini's Google Search grounding tool.

    Returns empty values if no key is configured. Tries the configured model
    first, then a known broadly available Flash model if that model is rejected.
    """
    key = (api_key or os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return "", []

    prompt = (
        "Pesquise na web usando Google Search e responda em português brasileiro. "
        "Priorize fontes oficiais e primárias, verifique datas e diferencie fatos confirmados "
        "de alegações. Não invente fontes. Para resultados eleitorais brasileiros, procure "
        "primeiro o TSE e os TREs. Faça uma síntese factual curta para ajudar outro assistente "
        "a responder à pergunta, preservando as fontes encontradas. Pergunta: "
        + re.sub(r"\s+", " ", query).strip()[:1000]
    )
    configured_model = (model or os.getenv("GOOGLE_SEARCH_MODEL") or DEFAULT_MODEL).strip()
    models = list(dict.fromkeys([configured_model, DEFAULT_MODEL]))
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=8.0)) as client:
        for model_name in models:
            url = GENERATE_CONTENT_URL.format(model=model_name)
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1800},
            }
            try:
                response = await client.post(
                    url,
                    params={"key": key},
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Google grounding returned an unexpected response")
                summary, citations = _extract_grounded_output(data)
                if summary or citations:
                    return summary, citations
                last_error = ValueError(f"Gemini model {model_name} returned no text or grounding citations")
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                # Do not retry the same model; try the known fallback model.
                print(
                    f"Google Search Grounding model={model_name} failed "
                    f"(status={status or 'n/a'}, error={type(exc).__name__})"
                )

    if last_error:
        raise last_error
    return "", []
