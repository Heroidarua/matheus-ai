"""Deterministic guard for requests that try to extract ADA-M internal secrets/configuration."""
from __future__ import annotations

import re
import unicodedata


_SECRET_TARGET = re.compile(
    r"\b(?:credencia(?:is|l)|chaves?\s+(?:de\s+)?api|api\s*keys?|tokens?|senhas?|passwords?|"
    r"secrets?|segredos?|cookies?|vari[aá]veis?\s+de\s+ambiente|environment\s+variables?|"
    r"\.env\b|arquivos?\s+de\s+configura[cç][aã]o|configura[cç][oõ]es?\s+internas?|"
    r"configura[cç][oõ]es?\s+(?:que\s+(?:voc[eê]|ada[- ]?m)\s+usa|atuais?|do\s+sistema|da\s+ada[- ]?m)|"
    r"par[aâ]metros?\s+(?:internos?|do\s+sistema)|prompt\s+(?:interno|de\s+sistema)|system\s+prompt|"
    r"chaves?\s+privadas?|private\s+keys?)\b",
    re.IGNORECASE,
)
_EXTRACTION_INTENT = re.compile(
    r"\b(?:mostr(?:e|ar)|revel(?:e|ar)|list(?:e|ar)|inform(?:e|ar)|"
    r"diga|dizer|forne[cç](?:a|er)|exib(?:a|ir)|imprim(?:a|ir)|"
    r"leia|ler|extraia|extrair|copie|copiar|export(?:e|ar)|"
    r"dump|cat|print|show|reveal|list|tell|give|output|read|extract|"
    r"quais|qual|que|o\s+que)\b",
    re.IGNORECASE,
)
_CURRENT_CONFIG = re.compile(
    r"\b(?:voc[eê]|ada[- ]?m|sistema|servidor|aplica[cç][aã]o|"
    r"est[aáo]\s+configurad[oa]s?|tem\s+configurad[oa]s?|"
    r"usa|utiliza|est[aáo]\s+usando|currently\s+configured|"
    r"configured\s+(?:keys?|tokens?|credentials?|secrets?))\b",
    re.IGNORECASE,
)


def is_sensitive_internal_config_request(message: str) -> bool:
    """Return True only when a message seeks current internal secrets/config values."""
    if not isinstance(message, str) or not message.strip():
        return False
    normalized = unicodedata.normalize("NFKC", message)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    has_env_file = bool(re.search(r"(?<![A-Za-z0-9_])\.env\b", normalized, re.IGNORECASE))
    if not _SECRET_TARGET.search(normalized) and not has_env_file:
        return False
    return bool(_EXTRACTION_INTENT.search(normalized) or _CURRENT_CONFIG.search(normalized))


SENSITIVE_REQUEST_REPLY = (
    "Não posso fornecer credenciais, segredos ou valores de configuração internos. "
    "Posso ajudar a configurar, testar ou corrigir um recurso sem expor esses dados."
)
