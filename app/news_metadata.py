"""Extract editorial provenance and publication-date evidence from article pages."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse


_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _date_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    candidate = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r"\b(\d{1,2})\s+de\s+([a-zçãé]+)\s+de\s+(20\d{2})\b", value, re.I)
    if match:
        month = _MONTHS.get(match.group(2).casefold())
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1))).isoformat()
            except ValueError:
                return ""
    match = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d{2})\b", value)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            return ""
    return ""


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonical = ""
        self.times = []
        self.jsonld = []
        self.visible = []
        self.h1 = []
        self.links = []
        self._hidden = 0
        self._script = False
        self._script_jsonld = False
        self._script_parts = []
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or values.get("itemprop") or "").casefold()
            if key and values.get("content"):
                self.meta[key] = values["content"].strip()
        elif tag == "link" and "canonical" in values.get("rel", "").casefold().split():
            self.canonical = values.get("href", "").strip()
        elif tag == "time" and values.get("datetime"):
            self.times.append(values["datetime"].strip())
        elif tag == "a" and values.get("href"):
            self.links.append((values.get("href", "").strip(), ""))
        if tag == "h1":
            self._in_h1 = True
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}:
            self._hidden += 1
        if tag == "script":
            self._script = True
            self._script_jsonld = "ld+json" in values.get("type", "").casefold()
            self._script_parts = []

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        if tag == "script":
            if self._script_jsonld:
                self.jsonld.append("".join(self._script_parts))
            self._script = False
            self._script_jsonld = False
            self._script_parts = []
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data):
        if self._script and self._script_jsonld:
            self._script_parts.append(data)
        if not self._hidden:
            text = " ".join(data.split())
            if text:
                self.visible.append(text)
                if self._in_h1:
                    self.h1.append(text)


def extract_article_metadata(html: str, page_url: str, feed_date: str = "") -> dict[str, str]:
    """Return conservative article metadata; never infer an exact date from crawl time."""
    parser = _MetadataParser()
    try:
        parser.feed((html or "")[:1_000_000])
    except (ValueError, TypeError):
        pass

    structured = []
    structured_headline = ""
    structured_publisher = ""
    structured_author = ""
    structured_types = []
    for raw in parser.jsonld:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in _walk_json(payload):
            item_type = item.get("@type", "")
            structured_types.extend(item_type if isinstance(item_type, list) else [item_type])
            if not structured_headline and item.get("headline"):
                structured_headline = str(item["headline"]).strip()
            if not structured_publisher:
                publisher = item.get("publisher")
                if isinstance(publisher, dict):
                    structured_publisher = str(publisher.get("name") or "").strip()
            if not structured_author:
                author = item.get("author")
                if isinstance(author, dict):
                    structured_author = str(author.get("name") or "").strip()
                elif isinstance(author, list) and author and isinstance(author[0], dict):
                    structured_author = str(author[0].get("name") or "").strip()
            if item.get("datePublished"):
                structured.append(_date_value(str(item["datePublished"])))

    meta_date = ""
    for key in (
        "article:published_time", "og:published_time", "datepublished",
        "datepublished", "pubdate", "publishdate", "parsely-pub-date",
        "dc.date.issued", "date",
    ):
        if parser.meta.get(key):
            meta_date = _date_value(parser.meta[key])
            if meta_date:
                break
    structured_date = next((value for value in structured if value), "")
    time_date = next((_date_value(value) for value in parser.times if _date_value(value)), "")
    visible_text = " ".join(parser.visible)
    visible_date = ""
    byline_window = visible_text[:700]
    date_context = re.search(
        r"(?:publicad[oa]|publicação|postad[oa]|atualizad[oa]|em)\s*[:\-]?\s*"
        r"(.{0,100}?(?:\d{1,2}\s+de\s+[a-zçãé]+\s+de\s+20\d{2}|\d{1,2}[/.]\d{1,2}[/.]20\d{2}|20\d{2}-\d{2}-\d{2}))",
        byline_window,
        re.I,
    )
    if date_context:
        visible_date = _date_value(date_context.group(1))
    if not visible_date:
        visible_date = _date_value(byline_window)

    page_date = structured_date or meta_date or time_date or visible_date
    page_date_source = (
        "datePublished (JSON-LD)" if structured_date else
        "metadado de publicação" if meta_date else
        "elemento time" if time_date else
        "data visível próxima ao início da página" if visible_date else ""
    )
    page_conflict = bool(structured_date and visible_date and structured_date != visible_date)

    feed_date = _date_value(feed_date)
    if page_conflict:
        date_status = "conflito_na_pagina"
    elif page_date and feed_date:
        try:
            delta = abs((date.fromisoformat(page_date) - date.fromisoformat(feed_date)).days)
        except ValueError:
            delta = 99
        date_status = "confirmada" if delta <= 1 else "divergente_do_feed"
    elif page_date:
        date_status = "confirmada_na_pagina"
    elif feed_date:
        date_status = "somente_feed"
    else:
        date_status = "sem_data_verificavel"

    publisher = (
        parser.meta.get("og:site_name")
        or parser.meta.get("application-name")
        or structured_publisher
    )
    author = parser.meta.get("author") or parser.meta.get("article:author") or structured_author
    headline = " ".join(parser.h1).strip() or structured_headline

    page_host = (urlparse(page_url).hostname or "").lower().removeprefix("www.")
    canonical = parser.canonical
    if canonical and not canonical.startswith(("http://", "https://")):
        from urllib.parse import urljoin
        canonical = urljoin(page_url, canonical)
    canonical_host = (urlparse(canonical).hostname or "").lower().removeprefix("www.") if canonical else ""
    original_url = canonical if canonical and canonical_host and canonical_host != page_host else ""

    lower = (visible_text[:12000] + " " + " ".join(parser.meta.values()) + " " + page_url).casefold()
    sponsored_markers = (
        "conteúdo patrocinado", "conteudo patrocinado", "publieditorial",
        "publicidade", "sponsored content", "advertorial", "conteúdo de marca",
        "conteudo de marca", "parceria paga", "conteúdo pago", "conteudo pago",
    )
    corporate_markers = (
        "agência dino", "agencia dino", "dino conteúdo", "dino conteudo",
        "pr newswire", "prnewswire", "business wire", "mundo corporativo",
        "assessoria de imprensa", "comunicado à imprensa", "comunicado a imprensa",
        "press release", "release enviado", "conteúdo enviado por", "conteudo enviado por",
        "enviado pela assessoria", "sala de imprensa",
    )
    syndicated_patterns = (
        r"com informações (?:da|de) (agência brasil|agencia brasil|reuters|afp|associated press)",
        r"(?:fonte|via|reprodução de|reproducao de)\s*:\s*(reuters|afp|associated press|agência brasil|agencia brasil)",
        r"conteúdo distribuído por\s+(reuters|afp|associated press|agência brasil|agencia brasil)",
    )
    agency = ""
    for pattern in syndicated_patterns:
        match = re.search(pattern, lower)
        if match:
            agency = match.group(1)
            break
    if any(marker in lower for marker in sponsored_markers):
        editorial_type = "patrocinado"
        editorial_label = "Conteúdo patrocinado / publieditorial"
    elif any(marker in lower for marker in corporate_markers):
        editorial_type = "corporativo"
        editorial_label = "Release ou conteúdo corporativo"
        if "dino" in lower:
            agency = "Agência Dino"
        elif "pr newswire" in lower or "prnewswire" in lower:
            agency = "PR Newswire"
        elif "business wire" in lower:
            agency = "Business Wire"
    elif agency and page_host not in {"agenciabrasil.ebc.com.br", "reuters.com", "afp.com", "apnews.com"}:
        editorial_type = "republicado"
        editorial_label = "Conteúdo republicado de agência"
    elif author or any(kind in {"NewsArticle", "Article"} for kind in structured_types):
        editorial_type = "jornalismo"
        editorial_label = "Reportagem / conteúdo editorial"
    else:
        editorial_type = "indeterminado"
        editorial_label = "Natureza editorial não confirmada"

    original_name = agency or (
        canonical_host if original_url else ""
    )
    feed_status = "presente" if feed_date else "ausente"
    return {
        "page_headline": headline[:240],
        "publisher": (publisher or page_host)[:120],
        "author": author[:120],
        "published_date": page_date,
        "published_date_source": page_date_source,
        "feed_published_date": feed_date,
        "date_status": date_status,
        "editorial_type": editorial_type,
        "editorial_label": editorial_label,
        "original_source_name": original_name[:120],
        "original_source_url": original_url[:2000],
        "canonical_url": canonical[:2000],
        "has_feed_date": feed_status,
    }
