"""Pesquisa verificável: classificação de intenção, expansão e ranking de fontes.

Este módulo não afirma que uma fonte é verdadeira; ele prioriza resultados relevantes
e fontes primárias para que o modelo possa avaliar evidências com transparência.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


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
    "elections": (
        "tse.jus.br", "tre-", "camara.leg.br", "senado.leg.br",
    ),
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
        "agenciabrasil.ebc.com.br", "gov.br",
    ),
}


def classify_research_topic(query: str) -> str:
    """Classifica a intenção principal, dando prioridade a pedidos explícitos de notícia."""
    text = re.sub(r"\\s+", " ", query.casefold()).strip()
    election_terms = ("eleição", "eleições", "eleitoral", "apura", "votos válidos", "resultado eleitoral", "quem ganhou", "quem venceu", "foi eleito")
    if any(term in text for term in election_terms):
        return "elections"
    if any(term in text for term in ("notícia", "notícias", "news", "manchetes", "principais notícias")):
        return "news"
    if any(keyword in text for keyword in TOPIC_KEYWORDS["science"]):
        return "science"
    if any(keyword in text for keyword in TOPIC_KEYWORDS["technology"]):
        return "technology"
    if any(term in text for term in ("aconteceu", "últimas", "hoje", "ontem", "agora", "recente", "atual", "breaking", "latest", "today")):
        return "news"
    return "general"


def build_search_query(query: str) -> str:
    """Expande a consulta com pistas de fonte primária, preservando a pergunta."""
    original = re.sub(r"\s+", " ", query).strip()[:350]
    if not original:
        return ""
    topic = classify_research_topic(original)
    suffixes = {
        "elections": " resultado oficial fonte primária TSE TRE",
        "technology": " documentação oficial release notes",
        "science": " artigo científico fonte primária universidade órgão científico",
        "news": " notícias recentes fontes confiáveis data publicação fonte oficial",
        "general": "",
    }
    # Não repete uma expansão que já tenha sido aplicada pelo chamador.
    return (original + suffixes[topic])[:500]


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
    domains = TRUSTED_DOMAINS.get(topic, ())
    return 2 if any(_host_matches(host, domain) for domain in domains) else 0


def result_relevance_score(query: str, item: dict[str, str]) -> int:
    """Pontua correspondência entre a pergunta e título/trecho; não usa o corpo como instrução."""
    query_tokens = {
        token for token in re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)
        if len(token) >= 4
    }
    text = " ".join((
        item.get("title", ""), item.get("snippet", ""), item.get("page_text", "")
    )).casefold()
    if not query_tokens or not text.strip():
        return 0
    matched = sum(1 for token in query_tokens if token in text)
    return min(10, matched * 2)


def is_relevant_result(query: str, item: dict[str, str]) -> bool:
    """Descarta resultados que não parecem responder à pergunta."""
    title = item.get("title", "").casefold()
    snippet = item.get("snippet", "").casefold()
    combined = title + " " + snippet
    topic = classify_research_topic(query)

    if topic in {"elections", "news", "technology", "science"}:
        # Evita dicionários, traduções e páginas lexicais em pesquisas factuais.
        lexical_only = any(term in combined for term in (
            "significado da palavra", "definição de", "tradução de", "sinônimo de",
            "dicionário", "dictionary", "conjugação do verbo", "word meaning",
        ))
        if lexical_only:
            return False

    if topic == "elections":
        election_terms = ("elei", "presidente", "presidencial", "tse", "tribunal superior eleitoral", "apura", "voto", "candidato", "resultado", "reeleito")
        if not any(term in combined for term in election_terms):
            return False

    # Busca pode usar siglas/sinônimos (IA/AI) e manchetes curtas. Aceita uma
    # correspondência temática razoável, mas nunca aceita páginas lexicais acima.
    score = result_relevance_score(query, item)
    trusted = source_trust_score(item, topic) > 0
    if trusted:
        return True
    if topic == "news":
        topical_terms = ("notícia", "noticias", "news", "inteligência artificial", "artificial intelligence", " ai ", "ia", "tecnologia", "lançamento", "anunciou", "hoje", "today", "latest")
        return score >= 2 or any(term in combined for term in topical_terms)
    return score >= 2


def rank_results(query: str, items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Ordena por relevância e origem, remove duplicatas e exclui resultados claramente irrelevantes."""
    topic = classify_research_topic(query)
    ranked: list[tuple[int, int, dict[str, str]]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url", "").strip()
        if not url or url in seen or not is_relevant_result(query, item):
            continue
        seen.add(url)
        ranked.append((
            source_trust_score(item, topic),
            result_relevance_score(query, item),
            item,
        ))
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [item for _, _, item in ranked]
