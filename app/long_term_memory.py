"""Memória de longo prazo/contextual da ADA-M, com PostgreSQL e fallback volátil."""
from __future__ import annotations
import os, re
from typing import Any
import psycopg

_LIMIT = 80
_VOLATILE: dict[str, list[dict[str, str]]] = {}
_SENSITIVE = re.compile(r"\b(cpf|rg|senha|password|token|api[ _-]?key|chave secreta|cart[aã]o|cvv|diagn[oó]stico|medicamento|doen[cç]a|endereço residencial)\b", re.I)
_SECRET = re.compile(r"(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,})", re.I)
_TRIGGERS = (
 r"\b(meu projeto|minha empresa|meu site|meu aplicativo|minha aplicação)\b",
 r"\b(estou desenvolvendo|estou criando|estou construindo|trabalho com)\b",
 r"\b(prefiro|minha preferência|gosto de|não gosto de|nao gosto de)\b",
 r"\b(quero que você (?:sempre|nunca)|quero que voce (?:sempre|nunca)|sempre|nunca|não quero|nao quero)\b",
 r"\b(meu objetivo|minha meta|estou usando|uso atualmente)\b",
 r"\b(lembre-se|lembre que|guarde que)\b",
)
_STOP = {"para","como","quando","onde","porque","qual","quais","isso","essa","esse","com","sem","uma","uns","que","por","mais","sobre","quero","preciso","meu","minha","voce","você"}

def _db():
    url=os.getenv("DATABASE_URL","").strip()
    return psycopg.connect(url, connect_timeout=4) if url else None

def _ensure(cur):
    cur.execute("""CREATE TABLE IF NOT EXISTS ada_m_long_term_memory (
      id BIGSERIAL PRIMARY KEY, owner_id TEXT NOT NULL, content TEXT NOT NULL,
      category TEXT NOT NULL DEFAULT 'contexto', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_used_at TIMESTAMPTZ, use_count INTEGER NOT NULL DEFAULT 0,
      UNIQUE(owner_id, content))""")
    cur.execute("CREATE INDEX IF NOT EXISTS ada_m_long_term_memory_owner_idx ON ada_m_long_term_memory(owner_id, created_at DESC)")

def extract_memory_candidate(text: str) -> str | None:
    value=re.sub(r"\s+"," ",str(text or "")).strip()
    if not 20 <= len(value) <= 420 or _SENSITIVE.search(value) or _SECRET.search(value): return None
    if not any(re.search(p,value,re.I) for p in _TRIGGERS): return None
    if value.endswith("?") or re.match(r"^(como|por que|qual|quais|pode|poderia)\b",value,re.I): return None
    return value

def remember(owner_id: str, user_text: str) -> bool:
    value=extract_memory_candidate(user_text)
    if not value: return False
    category="preferência" if re.search(r"prefiro|minha preferência|gosto de|não gosto|nao gosto",value,re.I) else "projeto/contexto"
    conn=_db()
    if conn is None:
        items=_VOLATILE.setdefault(owner_id,[])
        if not any(x["content"].casefold()==value.casefold() for x in items): items.append({"content":value,"category":category}); del items[:-_LIMIT]
        return True
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur)
                cur.execute("INSERT INTO ada_m_long_term_memory(owner_id,content,category) VALUES(%s,%s,%s) ON CONFLICT(owner_id,content) DO NOTHING",(owner_id,value,category))
        return True
    finally: conn.close()

def retrieve(owner_id: str, query: str, limit: int=8) -> list[str]:
    conn=_db()
    if conn is None: items=list(_VOLATILE.get(owner_id,[]))
    else:
        try:
            with conn:
                with conn.cursor() as cur:
                    _ensure(cur); cur.execute("SELECT id,content,category FROM ada_m_long_term_memory WHERE owner_id=%s ORDER BY created_at DESC LIMIT %s",(owner_id,_LIMIT))
                    rows=cur.fetchall()
            items=[{"id":r[0],"content":r[1],"category":r[2]} for r in rows]
        finally: conn.close()
    words={w for w in re.findall(r"[a-zá-ú0-9][a-zá-ú0-9+.#_-]{2,}",query.casefold()) if w not in _STOP}
    ranked=[]
    for i,item in enumerate(items):
        body=item["content"].casefold()
        overlap=sum(1 for w in words if w in body)
        if words and overlap: ranked.append((overlap,i,item))
    ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)
    chosen=[x[2] for x in ranked[:limit]]
    if conn is not None:
        ids=[x["id"] for x in chosen if x.get("id") is not None]
        if ids:
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE ada_m_long_term_memory SET last_used_at=NOW(),use_count=use_count+1 WHERE owner_id=%s AND id=ANY(%s)",(owner_id,ids))
            except Exception as exc: print(f"Memory usage update skipped ({type(exc).__name__})")
    return [f"[{x['category']}] {x['content']}" for x in chosen]

def list_memories(owner_id: str) -> list[str]:
    conn=_db()
    if conn is None: return [x["content"] for x in _VOLATILE.get(owner_id,[])]
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur); cur.execute("SELECT content FROM ada_m_long_term_memory WHERE owner_id=%s ORDER BY created_at DESC LIMIT %s",(owner_id,_LIMIT))
                return [r[0] for r in cur.fetchall()]
    finally: conn.close()

def forget_all(owner_id: str) -> int:
    conn=_db()
    if conn is None: return len(_VOLATILE.pop(owner_id,[]))
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure(cur); cur.execute("DELETE FROM ada_m_long_term_memory WHERE owner_id=%s",(owner_id,)); return cur.rowcount
    finally: conn.close()

def storage_status() -> str:
    conn=_db()
    if conn is None: return "temporária: DATABASE_URL não configurado"
    try:
        with conn:
            with conn.cursor() as cur: _ensure(cur); cur.execute("SELECT 1"); cur.fetchone()
        return "PostgreSQL persistente"
    except Exception as exc: return f"PostgreSQL indisponível ({type(exc).__name__})"
    finally: conn.close()
