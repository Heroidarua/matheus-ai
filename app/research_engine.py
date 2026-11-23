"""Pesquisa verificável: classificação de intenção, expansão e ranking de fontes."""
from __future__ import annotations

import re
from urllib.parse import urlparse


MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
_DATE_FILTER_RE = re.compile(
    r"\b(?:" + "|".join(MONTH_NAMES) + r")\s+(?:de\s+)?20\d{2}\b"
    r"|\b20\d{2}\s+(?:de\s+)?(?:" + "|".join(MONTH_NAMES) + r")\b",
    re.IGNORECASE,
)
NEWS_INTENT_TERMS = (
    "notícia", "notícias", "noticia", "noticias", "news", "manchete",
    "manchetes", "reportagem", "reportagens", "matéria jornalística",
    "matérias jornalísticas", "jornal", "jornais",
)
TOPIC_KEYWORDS = {
    "elections": (
        "eleição", "eleições", "eleitoral", "apura", "votos válidos",
        "resultado eleitoral", "quem ganhou", "quem venceu", "foi eleito",
    ),
    "news": (
        "notícia", "notícias", "aconteceu", "últimas", "hoje", "ontem",
        "agora", "recente", "atual", "breaking", "latest", "today",
    ),
    "technology": (
        "tecnologia", "inteligência artificial", "ia ", "software", "hardware",
        "lançamento", "versão", "vulnerabilidade", "cibersegurança", "github",
        "android", "linux", "openai", "modelo de linguagem",
    ),
    "science": (
        "ciência", "científico", "científica", "estudo", "pesquisa científica",
        "artigo científico", "ensaio clínico", "descoberta", "astronomia",
        "física", "biologia", "clima", "saúde pública",
    ),
}
TRUSTED_DOMAINS = {
    "elections": ("tse.jus.br", "tre-", "camara.leg.br", "senado.leg.br"),
    "technology": (
        "docs.python.org", "developer.mozilla.org", "learn.microsoft.com",
        "github.com", "openai.com", "cloudflare.com", "developer.android.com",
        "kernel.org", "ietf.org",
    ),
    "science": (
        "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov", "nih.gov",
        "who.int", "nasa.gov", "esa.int", "noaa.gov", "gov.br",
        "arxiv.org", "doi.org",
    ),
    "news": (
        "reuters.com", "apnews.com", "bbc.com", "g1.globo.com",
        "agenciabrasil.ebc.com.br", "gov.br", "estadao.com.br",
        "folha.uol.com.br", "valor.globo.com", "cnn.com",
    ),
}
_STOPWORDS = {
    "sobre", "para", "com", "sem", "uma", "umas", "uns", "dos", "das",
    "que", "qual", "quais", "como", "onde", "quando", "porque", "porquê",
    "pesquise", "pesquisar", "pesquisa", "internet", "noticia", "noticias",
    "notícia", "notícias", "news", "hoje", "ontem", "agora", "atual",
    "atuais", "última", "últimas", "ultimas", "recente", "recentes",
    "publicada", "publicadas", "publicado", "publicados", "em", "no", "na",
    "nos", "nas", "de", "do", "da", "e", "ou", "a", "o", "as", "os",
    "brasil", "brasileiro", "brasileira", "brasileiros", "brasileiras",
    *MONTH_NAMES,
}


def has_explicit_date_filter(query: str) -> bool:
    """Detecta mês/ano explícito para não aplicar filtros de últimas 24 horas."""
    return bool(_DATE_FILTER_RE.search(query or ""))


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[^\W_]+", (text or "").casefold(), flags=re.UNICODE)
        if len(token) >= 4
    }


def _subject_tokens(query: str) -> set[str]:
    return _tokens(query) - _STOPWORDS - {str(year) for year in range(2000, 2101)}


def _mentions_ai(query: str) -> bool:
    text = (query or "").casefold()
    return bool(
        re.search(r"\b(?:ia|ai)\b", text)
        or "inteligência artificial" in text
        or "artificial intelligence" in text
    )


def _candidate_mentions_ai(text: str) -> bool:
    normalized = (text or "").casefold()
    return bool(
        re.search(r"\b(?:ia|ai)\b", normalized)
        or "inteligência artificial" in normalized
        or "artificial intelligence" in normalized
    )


def classify_research_topic(query: str) -> str:
    """Classifica a intenção antes do assunto, evitando confundir notícias de IA com documentação."""
    text = re.sub(r"\s+", " ", (query or "").casefold()).strip()
    election_terms = (
        "eleição", "eleições", "eleitoral", "apura", "votos válidos",
        "resultado eleitoral", "quem ganhou", "quem venceu", "foi eleito",
    )
    if any(term in text for term in election_terms):
        return "elections"
    if any(term in text for term in NEWS_INTENT_TERMS):
        return "news"
    technical_lookup_terms = ("documentação", "tutorial", "manual", "como instalar", "como usar")
    if has_explicit_date_filter(text) and not any(term in text for term in technical_lookup_terms):
        if any(keyword in text for keyword in TOPIC_KEYWORDS["technology"]):
            return "news"
    if any(keyword in text for keyword in TOPIC_KEYWORDS["science"]):
        return "science"
    if any(keyword in text for keyword in TOPIC_KEYWORDS["technology"]):
        return "technology"
    if any(term in text for term in (
        "aconteceu", "últimas", "hoje", "ontem", "agora", "recente",
        "atual", "breaking", "latest", "today",
    )):
        return "news"
    return "general"


def build_search_query(query: str) -> str:
    """Expande a consulta com pistas adequadas à intenção, preservando datas."""
    original = re.sub(r"\s+", " ", (query or "")).strip()[:350]
    if not original:
        return ""
    topic = classify_research_topic(original)
    if topic == "news":
        suffix = (
            " reportagens jornalísticas veículos de imprensa fontes confiáveis"
            if has_explicit_date_filter(original)
            else " notícias atuais veículos de imprensa fontes confiáveis data de publicação"
        )
    else:
        suffix = {
            "elections": " resultado oficial fonte primária TSE TRE",
            "technology": " documentação oficial release notes",
            "science": " artigo científico fonte primária universidade órgão científico",
            "general": "",
        }[topic]
    return (original + suffix)[:500]


def _host_matches(host: str, domain: str) -> bool:
    domain = domain.strip().lower()
    if not domain:
        return False
    return host == domain or host.endswith("." + domain) or (
        domain.endswith("-") and domain in host
    )


def source_trust_score(item: dict[str, str], topic: str) -> int:
    """Pontuação heurística de origem: 2 para domínio primário/confiável, 0 caso contrário."""
    try:
        host = (urlparse(item.get("url", "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return 0
    return 2 if any(_host_matches(host, domain) for domain in TRUSTED_DOMAINS.get(topic, ())) else 0


def result_relevance_score(query: str, item: dict[str, str]) -> int:
    """Pontua correspondência entre o assunto pedido e título/trecho da página."""
    query_tokens = _subject_tokens(query)
    text = " ".join((
        item.get("title", ""), item.get("snippet", ""), item.get("page_text", "")
    )).casefold()
    if not text.strip():
        return 0
    matched = sum(1 for token in query_tokens if token in text)
    score = min(10, matched * 2)
    if _mentions_ai(query) and _candidate_mentions_ai(text):
        score += 4
    return score


def is_relevant_result(query: str, item: dict[str, str]) -> bool:
    """Descarta páginas lexicais e exige correspondência com o assunto central."""
    title = item.get("title", "").casefold()
    snippet = item.get("snippet", "").casefold()
    combined = title + " " + snippet
    topic = classify_research_topic(query)

    if topic in {"elections", "news", "technology", "science"}:
        lexical_only = any(term in combined for term in (
            "significado da palavra", "definição de", "definicao de",
            "tradução de", "traducao de", "sinônimo de", "sinonimo de",
            "dicionário", "dicionario", "dictionary", "conjugação do verbo",
            "word meaning", "what does the word mean",
        ))
        if lexical_only:
            return False

    if topic == "elections":
        election_terms = (
            "elei", "presidente", "presidencial", "tse",
            "tribunal superior eleitoral", "apura", "voto", "candidato",
            "resultado", "reeleito",
        )
        return any(term in combined for term in election_terms)

    if topic == "news":
        # Domínio confiável não é passe livre: o conteúdo ainda precisa tratar do assunto.
        if _mentions_ai(query) and not _candidate_mentions_ai(combined):
            return False
        subject = _subject_tokens(query)
        if subject:
            matched = sum(1 for token in subject if token in combined)
            return matched >= 1 or (_mentions_ai(query) and _candidate_mentions_ai(combined))
        topical_terms = (
            "notícia", "noticias", "news", "reportagem", "jornal",
            "anunciou", "anuncia", "publicou", "publicado", "publicada",
            "hoje", "today", "latest",
        )
        return bool(title.strip() or snippet.strip()) and (
            any(term in combined for term in topical_terms)
            or source_trust_score(item, topic) > 0
        )

    meaningful_tokens = _subject_tokens(query)
    if not meaningful_tokens:
        return bool(title.strip() or snippet.strip())
    if source_trust_score(item, topic) > 0:
        return True
    return result_relevance_score(query, item) >= 2


def rank_results(query: str, items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Ordena por correspondência temática, depois confiabilidade; remove duplicatas."""
    topic = classify_research_topic(query)
    ranked: list[tuple[int, int, dict[str, str]]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url", "").strip()
        if not url or url in seen or not is_relevant_result(query, item):
            continue
        seen.add(url)
        ranked.append((
            result_relevance_score(query, item),
            source_trust_score(item, topic),
            item,
        ))
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [item for _, _, item in ranked]
