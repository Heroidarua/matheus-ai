"""Google Search Grounding adapter.

Uses Gemini only as a web-research tool. ADA-M's configured chat model remains
responsible for the final answer. API keys are read only from server environment.
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_MODEL = "gemini-3.8-flash"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


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
    """Parse model output and URL citation annotations from the Interactions API."""
    output_parts: list[str] = []
    citations: list[dict[str, str]] = []

    for step in payload.get("steps", []) or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for block in step.get("content", []) or []:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            block_text = block.get("text")
            if not isinstance(block_text, str):
                continue
            output_parts.append(block_text)
            annotations = block.get("annotations", []) or []
            for annotation in annotations:
                if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                    continue
                url = str(annotation.get("url", "")).strip()
                title = str(annotation.get("title", "")).strip()
                if not _public_http_url(url):
                    continue
                start = annotation.get("start_index", 0)
                end = annotation.get("end_index", 0)
                try:
                    excerpt = block_text[max(0, int(start)):max(0, int(end))]
                except (TypeError, ValueError):
                    excerpt = ""
                item = {
                    "title": (title or url)[:200],
                    "url": url[:2000],
                    "snippet": re.sub(r"\s+", " ", excerpt).strip()[:500],
                }
                if not any(existing["url"] == item["url"] for existing in citations):
                    citations.append(item)

    summary = re.sub(r"\n{3,}", "\n\n", "\n".join(output_parts)).strip()
    return summary[:6000], citations[:6]


async def google_grounded_search(
    query: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Search the live web through Google grounding and return summary + cited URLs.

    Returns an empty summary and list when no key is configured. Provider failures
    are raised to the caller so it can log the issue and use existing fallbacks.
    """
    key = (api_key or os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return "", []

    prompt = (
        "Pesquise na web usando Google Search e responda em português brasileiro. "
        "Priorize fontes oficiais e primárias, verifique datas e diferencie fatos confirmados "
        "de alegações. Não invente fontes. Faça uma síntese factual curta para ajudar outro "
        "assistente a responder à pergunta, preservando os links citados. Pergunta: "
        + re.sub(r"\s+", " ", query).strip()[:1000]
    )
    payload = {
        "model": (model or os.getenv("GOOGLE_SEARCH_MODEL") or DEFAULT_MODEL).strip(),
        "input": prompt,
        "tools": [{"type": "google_search"}],
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=8.0)) as client:
        response = await client.post(INTERACTIONS_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Google grounding returned an unexpected response")
    return _extract_grounded_output(data)
