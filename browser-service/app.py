"""Isolated Chromium browser service for ADA-M.

The service accepts only authenticated, allow-listed browser actions. Every
browser session gets its own isolated Playwright context and is keyed by the
opaque ADA-M server-side session identifier.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import ipaddress
import os
import re
import socket
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

API_KEY = os.getenv("ADA_BROWSER_API_KEY", "").strip()
MAX_SESSIONS = max(1, min(int(os.getenv("BROWSER_MAX_SESSIONS", "1")), 10))
MAX_TABS = max(1, min(int(os.getenv("BROWSER_MAX_TABS", "1")), 4))
SESSION_TTL = max(60, min(int(os.getenv("BROWSER_SESSION_TTL", "1800")), 86400))
ACTION_TIMEOUT_MS = max(3000, min(int(os.getenv("BROWSER_ACTION_TIMEOUT_MS", "15000")), 30000))
MAX_TEXT_CHARS = 12000
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


@dataclass
class BrowserSession:
    context: BrowserContext
    pages: list[Page] = field(default_factory=list)
    active_page: int = 0
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


sessions: dict[str, BrowserSession] = {}
browser: Browser | None = None
playwright = None


class BrowserAction(BaseModel):
    session_id: str = Field(min_length=20, max_length=128)
    action: str = Field(min_length=2, max_length=24)
    url: str | None = Field(default=None, max_length=2048)
    selector: str | None = Field(default=None, max_length=1000)
    text: str | None = Field(default=None, max_length=5000)
    value: str | None = Field(default=None, max_length=2000)
    key: str | None = Field(default=None, max_length=40)
    tab: int | None = Field(default=None, ge=0, le=7)
    index: int | None = Field(default=None, ge=0, le=79)
    full_page: bool = False
    delta_y: int = Field(default=700, ge=-3000, le=3000)


def build_scroll_evidence(requested_delta_y: int, before: float, after: float, visible_text: str) -> dict[str, Any]:
    """Build explicit evidence distinguishing a requested wheel action from actual page movement."""
    actual_delta_y = after - before
    return {
        "requested_delta_y": requested_delta_y,
        "scroll_y_before": before,
        "scroll_y_after": after,
        "actual_delta_y": actual_delta_y,
        "scrolled": actual_delta_y != 0,
        "visible_text": visible_text[:5000],
    }


async def is_public_url(value: str) -> bool:
    """Reject non-HTTP URLs, credentials, local names, and non-public DNS targets."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443, 8080, 8443):
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test")):
            return False
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            # Chromium aceita algumas formas abreviadas/numéricas de IPv4 que
            # ipaddress não interpreta como endereço literal; não permita que
            # esses valores sejam tratados como nomes DNS públicos.
            if re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+|[0-9.]+)", host):
                return False
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
        return bool(addresses) and all(address.is_global for address in addresses)
    except (ValueError, OSError, socket.gaierror):
        return False


async def guard_request(route) -> None:
    request_url = route.request.url
    # Permite apenas fontes incorporadas em data URI; outros esquemas continuam
    # bloqueados para preservar a proteção contra acesso a recursos locais.
    embedded_font = (
        route.request.resource_type == "font"
        and bool(re.match(
            r"^data:(?:font/(?:woff2?|ttf|otf)|application/(?:font-woff|vnd\.ms-fontobject))(?:;|,)",
            request_url,
            re.IGNORECASE,
        ))
    )
    if embedded_font:
        await route.continue_()
        return
    if not await is_public_url(request_url):
        await route.abort("blockedbyclient")
        return
    await route.continue_()


async def cleanup_expired() -> None:
    now = time.monotonic()
    expired = [key for key, value in sessions.items() if now - value.last_used > SESSION_TTL]
    for key in expired:
        item = sessions.pop(key, None)
        if item:
            try:
                await item.context.close()
            except Exception:
                pass


async def _track_new_page(session: BrowserSession, page: Page) -> None:
    if page in session.pages:
        return
    if len(session.pages) >= MAX_TABS:
        await page.close()
        return
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    session.pages.append(page)
    session.active_page = len(session.pages) - 1


async def create_session(session_id: str) -> BrowserSession:
    if browser is None:
        raise HTTPException(status_code=503, detail="Navegador ainda não inicializado.")
    await cleanup_expired()
    if session_id not in sessions and len(sessions) >= MAX_SESSIONS:
        raise HTTPException(status_code=429, detail="Limite de sessões de navegador atingido. Tente novamente em instantes.")
    context = await browser.new_context(
        viewport={"width": 1365, "height": 900},
        locale="pt-BR",
        timezone_id="America/Manaus",
        accept_downloads=False,
        service_workers="block",
    )
    await context.route("**/*", guard_request)
    page = await context.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    session = BrowserSession(context=context, pages=[page])
    context.on("page", lambda new_page: asyncio.create_task(_track_new_page(session, new_page)))
    sessions[session_id] = session
    return session


def is_readable_content_type(value: str | None) -> bool:
    """Only expose human-readable page bodies to the agent; never leak binary bytes."""
    content_type = (value or "").split(";", 1)[0].strip().lower()
    return content_type in {
        "text/html", "text/plain", "application/xhtml+xml",
        "application/json", "application/ld+json"
    }


async def extract_page_content(page: Page) -> dict[str, Any]:
    """Extrai conteúdo visível e útil, sem scripts, estilos, navegação ou texto técnico."""
    return await page.evaluate(r"""() => {
        const preferred = document.querySelector("main, [role='main'], article");
        const root = preferred || document.body;
        if (!root) return {title: document.title || "", text: "", headings: [], links: []};

        const clone = root.cloneNode(true);
        const originals = [root, ...root.querySelectorAll("*")];
        const copies = [clone, ...clone.querySelectorAll("*")];

        clone.querySelectorAll(
          "script, style, noscript, template, svg, canvas, iframe, object, embed, nav, footer, aside, form, [hidden], [aria-hidden='true']"
        ).forEach(el => el.remove());
        if (!preferred) clone.querySelectorAll("header").forEach(el => el.remove());

        for (let i = Math.min(originals.length, copies.length) - 1; i >= 0; i--) {
          const original = originals[i];
          const copy = copies[i];
          if (!copy || !copy.isConnected) continue;
          const style = window.getComputedStyle(original);
          if (style.display === "none" || style.visibility === "hidden" ||
              style.opacity === "0" || original.getAttribute("aria-hidden") === "true") {
            copy.remove();
          }
        }

        const clean = value => (value || "").replace(/\u00a0/g, " ")
          .replace(/[ \t]+/g, " ").replace(/\s+([,.;:!?])/g, "$1").trim();
        const raw = clone.innerText || clone.textContent || "";
        const lines = raw.split(/\n+/).map(clean).filter(Boolean);
        const uniqueLines = [];
        const seen = new Set();
        for (const line of lines) {
          if (line.length < 2 || line.length > 1200) continue;
          const key = line.toLocaleLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          uniqueLines.push(line);
        }

        const headings = [...clone.querySelectorAll("h1, h2, h3")]
          .map(el => clean(el.innerText || el.textContent))
          .filter((value, index, list) => value && list.indexOf(value) === index)
          .slice(0, 40);

        const links = [];
        const seenLinks = new Set();
        for (const a of root.querySelectorAll("a[href]")) {
          const style = window.getComputedStyle(a);
          if (style.display === "none" || style.visibility === "hidden" ||
              a.closest("[hidden], [aria-hidden='true'], nav, footer, aside")) continue;
          const label = clean(a.innerText || a.getAttribute("aria-label") || a.title);
          const href = a.href || "";
          if (!label || !/^https?:\/\//i.test(href) || seenLinks.has(href)) continue;
          seenLinks.add(href);
          links.push({text: label.slice(0, 180), url: href.slice(0, 2000)});
          if (links.length >= 30) break;
        }

        return {
          title: (document.title || "").slice(0, 300),
          text: uniqueLines.join("\n").slice(0, 12000),
          headings,
          links
        };
    }""")

def require_key(value: str | None) -> None:
    if not API_KEY:
        raise HTTPException(status_code=503, detail="ADA_BROWSER_API_KEY não foi configurada.")
    if not value or not hmac.compare_digest(value, API_KEY):
        raise HTTPException(status_code=401, detail="Chave interna inválida.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global browser, playwright
    if not API_KEY:
        raise RuntimeError("ADA_BROWSER_API_KEY é obrigatória; não inicie o serviço sem autenticação.")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking", "--disable-extensions", "--disable-default-apps", "--disable-sync", "--disable-gpu"])
    try:
        yield
    finally:
        for item in list(sessions.values()):
            await item.context.close()
        sessions.clear()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


app = FastAPI(title="ADA-M Browser Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"ok": "true", "service": "ada-m-browser", "browser": "ready" if browser else "starting"}


@app.post("/v1/action")
async def browser_action(payload: BrowserAction, x_ada_browser_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_key(x_ada_browser_key)
    if not SESSION_ID_RE.fullmatch(payload.session_id):
        raise HTTPException(status_code=400, detail="Identificador de sessão inválido.")
    allowed = {"open", "inspect", "click", "fill", "select", "press", "text", "screenshot", "tabs", "new_tab", "close_tab", "back", "forward", "refresh", "close", "hover", "scroll"}
    if payload.action not in allowed:
        raise HTTPException(status_code=400, detail="Ação de navegador não permitida.")

    session = sessions.get(payload.session_id)
    if session and time.monotonic() - session.last_used > SESSION_TTL:
        try:
            await session.context.close()
        except Exception:
            pass
        sessions.pop(payload.session_id, None)
        session = None
    if payload.action == "close":
        if session:
            await session.context.close()
            sessions.pop(payload.session_id, None)
        return {"ok": True, "closed": True}
    if session is None:
        session = await create_session(payload.session_id)

    async with session.lock:
        session.last_used = time.monotonic()
        if payload.tab is not None:
            if payload.tab >= len(session.pages):
                raise HTTPException(status_code=404, detail="A aba solicitada não existe.")
            session.active_page = payload.tab
        page = session.pages[session.active_page]
        try:
            if payload.action == "open":
                if not payload.url or not await is_public_url(payload.url):
                    raise HTTPException(status_code=400, detail="Informe uma URL HTTP(S) pública válida.")
                response = await page.goto(payload.url, wait_until="domcontentloaded", timeout=ACTION_TIMEOUT_MS)
                try:
                    await page.wait_for_load_state("networkidle", timeout=2500)
                except Exception:
                    pass
                await page.wait_for_timeout(450)
                content_type = response.headers.get("content-type", "") if response else ""
                readable = is_readable_content_type(content_type)
                extracted = await extract_page_content(page) if readable else {"title": (await page.title())[:300], "text": "", "headings": [], "links": []}
                result = {
                    "ok": True,
                    "url": page.url,
                    "title": extracted["title"],
                    "status": response.status if response else None,
                    "content_type": content_type.split(";", 1)[0][:120],
                    "text": extracted["text"][:MAX_TEXT_CHARS],
                    "headings": extracted["headings"],
                    "links": extracted["links"],
                }
                if not readable:
                    result["note"] = "A resposta não é uma página textual legível; nenhum conteúdo binário foi enviado ao agente."
                return result
            if payload.action == "inspect":
                elements = await page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").evaluate_all("""els => els.filter(el => el.getClientRects().length).slice(0, 80).map((el, index) => ({index, tag: el.tagName.toLowerCase(), text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\\s+/g, " ").slice(0, 180), role: el.getAttribute("role") || "", aria_label: el.getAttribute("aria-label") || "", href: el.getAttribute("href") || "", type: el.getAttribute("type") || "", name: el.getAttribute("name") || "", placeholder: el.getAttribute("placeholder") || ""}))""")
                return {"ok": True, "url": page.url, "title": (await page.title())[:300], "elements": elements}
            if payload.action == "hover":
                if not payload.selector and payload.index is None:
                    raise HTTPException(status_code=400, detail="A ação hover exige selector ou index obtido em inspect.")
                target = page.locator(payload.selector).first if payload.selector else page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").nth(payload.index)
                await target.hover()
                await page.wait_for_timeout(150)
                extracted = await extract_page_content(page)
                return {"ok": True, "url": page.url, **extracted}
            if payload.action == "scroll":
                scroll_y_before = await page.evaluate("() => window.scrollY")
                await page.mouse.wheel(0, payload.delta_y)
                await page.wait_for_timeout(350)
                scroll_y_after = await page.evaluate("() => window.scrollY")
                visible_text = await page.evaluate("""() => {
                    const width = window.innerWidth;
                    const height = window.innerHeight;
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    const lines = [];
                    const seen = new Set();
                    let node;
                    while ((node = walker.nextNode()) && lines.length < 60) {
                        const value = (node.nodeValue || "").replace(/\\s+/g, " ").trim();
                        if (value.length < 2 || seen.has(value)) continue;
                        const parent = node.parentElement;
                        if (!parent) continue;
                        const style = window.getComputedStyle(parent);
                        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") continue;
                        const range = document.createRange();
                        range.selectNode(node);
                        const rects = [...range.getClientRects()];
                        if (!rects.some(rect => rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < height && rect.right > 0 && rect.left < width)) continue;
                        seen.add(value);
                        lines.push(value.slice(0, 240));
                    }
                    return lines.join("\\n").slice(0, 5000);
                }""")
                return {
                    "ok": True,
                    "action": "scroll",
                    "url": page.url,
                    "title": (await page.title())[:300],
                    **build_scroll_evidence(payload.delta_y, scroll_y_before, scroll_y_after, visible_text),
                }
            if payload.action == "click":
                if not payload.selector and payload.index is None:
                    raise HTTPException(status_code=400, detail="A ação click exige selector ou index obtido em inspect.")
                target = page.locator(payload.selector).first if payload.selector else page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").nth(payload.index)
                await target.click()
                await page.wait_for_timeout(250)
                extracted = await extract_page_content(page)
                return {"ok": True, "url": page.url, **extracted}
            if payload.action == "fill":
                if not payload.selector and payload.index is None:
                    raise HTTPException(status_code=400, detail="A ação fill exige selector ou index.")
                target = page.locator(payload.selector).first if payload.selector else page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").nth(payload.index)
                await target.fill(payload.text or "")
                return {"ok": True, "filled": True, "selector": payload.selector}
            if payload.action == "select":
                if (not payload.selector and payload.index is None) or payload.value is None:
                    raise HTTPException(status_code=400, detail="A ação select exige selector ou index e value.")
                target = page.locator(payload.selector).first if payload.selector else page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").nth(payload.index)
                selected = await target.select_option(value=payload.value)
                return {"ok": True, "selected": selected}
            if payload.action == "press":
                if (not payload.selector and payload.index is None) or not payload.key:
                    raise HTTPException(status_code=400, detail="A ação press exige selector ou index e key.")
                target = page.locator(payload.selector).first if payload.selector else page.locator("a:visible,button:visible,input:visible,textarea:visible,select:visible,[role=button]:visible,[role=link]:visible").nth(payload.index)
                await target.press(payload.key)
                return {"ok": True, "pressed": payload.key}
            if payload.action == "text":
                extracted = await extract_page_content(page)
                return {"ok": True, "url": page.url, **extracted}
            if payload.action == "screenshot":
                image = await page.screenshot(type="png", full_page=payload.full_page, animations="disabled")
                if len(image) > 5 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Screenshot excede o limite de 5 MB; tente sem full_page.")
                return {"ok": True, "url": page.url, "image_base64": base64.b64encode(image).decode("ascii"), "mime_type": "image/png"}
            if payload.action == "tabs":
                return {"ok": True, "active": session.active_page, "tabs": [{"index": i, "url": p.url, "title": (await p.title())[:200]} for i, p in enumerate(session.pages)]}
            if payload.action == "new_tab":
                if len(session.pages) >= MAX_TABS:
                    raise HTTPException(status_code=429, detail=f"Limite de {MAX_TABS} abas por sessão atingido.")
                new_page = await session.context.new_page()
                new_page.set_default_timeout(ACTION_TIMEOUT_MS)
                session.pages.append(new_page)
                session.active_page = len(session.pages) - 1
                return {"ok": True, "tab": session.active_page, "tabs": len(session.pages)}
            if payload.action == "close_tab":
                if len(session.pages) <= 1:
                    raise HTTPException(status_code=400, detail="A última aba não pode ser fechada; use close para encerrar a sessão.")
                await page.close()
                session.pages.pop(session.active_page)
                session.active_page = min(session.active_page, len(session.pages) - 1)
                return {"ok": True, "active": session.active_page, "tabs": len(session.pages)}
            if payload.action == "back":
                await page.go_back(wait_until="domcontentloaded", timeout=ACTION_TIMEOUT_MS)
            elif payload.action == "forward":
                await page.go_forward(wait_until="domcontentloaded", timeout=ACTION_TIMEOUT_MS)
            elif payload.action == "refresh":
                await page.reload(wait_until="domcontentloaded", timeout=ACTION_TIMEOUT_MS)
            extracted = await extract_page_content(page)
            return {"ok": True, "url": page.url, **extracted}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Falha na ação do navegador: {type(exc).__name__}: {str(exc)[:240]}") from exc
