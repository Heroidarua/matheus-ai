import httpx
import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        ("https://sos01.com.br" + chr(0x2060), "https://sos01.com.br"),
        ("https://exa" + chr(0x200B) + "mple.com/path", "https://example.com/path"),
        ("https://example.com/" + chr(0xFEFF) + "page", "https://example.com/page"),
        ("https://example.com/path", "https://example.com/path"),
        ("[abrir](https://sos01.com.br" + chr(0x2060) + ")", "https://sos01.com.br"),
    ],
)
def test_normalize_tool_url_removes_invisible_unicode_characters(raw_url, expected):
    assert main.normalize_tool_url(raw_url) == expected

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_response_token_budget_does_not_shrink_output_by_ui_preference():
    assert main.response_token_budget("curta") == 32768
    assert main.response_token_budget("normal") == 32768
    assert main.response_token_budget("detalhada") == 32768


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("def multiplicacao(a, b):", True),
        ("```python\nprint('teste')", True),
        ("def multiplicacao(a, b):\n    return a * b", False),
        ("A resposta foi concluída corretamente.", False),
    ],
)
def test_response_looks_incomplete_detects_truncated_code(reply, expected):
    assert main.response_looks_incomplete(reply) is expected


def test_chat_request_defaults_to_detailed_response():
    request = main.ChatRequest(messages=[main.ChatMessage(role="user", content="Teste")])
    assert request.response_length == "detalhada"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(10 - 4) / 2", 3),
        ("-5 + 8", 3),
        ("2 ** 3", 8),
        ("10 % 3", 1),
    ],
)
def test_safe_calculate_accepts_basic_math(expression, expected):
    assert main.safe_calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo unsafe')",
        "open('/etc/passwd').read()",
        "2 ** 100",
        "1 / 0",
    ],
)
def test_safe_calculate_rejects_unsafe_or_invalid_expressions(expression):
    with pytest.raises((ValueError, SyntaxError, ZeroDivisionError, OverflowError)):
        main.safe_calculate(expression)


def test_safe_calculate_limits_expression_length():
    with pytest.raises(ValueError, match="longa"):
        main.safe_calculate("1" * 121)


def test_content_as_text_handles_text_and_parts():
    assert main.content_as_text("hello") == "hello"
    assert main.content_as_text([
        {"type": "text", "text": "linha 1"},
        {"type": "image", "data": "ignored"},
        {"type": "text", "text": "linha 2"},
    ]) == "linha 1\nlinha 2"




@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Quem ganhou a eleição 2026?", True),
        ("Qual foi o resultado da eleição?", True),
        ("Quais são as notícias de hoje?", True),
        ("O que aconteceu ontem no Brasil?", True),
        ("Explique o que é uma eleição presidencial", True),
        ("Como faço uma lista em Python?", False),
        ("Me ajude a escrever um poema", False),
    ],
)
def test_requires_live_search_for_current_or_election_questions(question, expected):
    assert main.requires_live_search(question) is expected


def test_current_local_date_has_iso_date_format():
    assert len(main.current_local_date()) >= 10
    assert main.current_local_date()[4] == "-"
    assert main.current_local_date()[7] == "-"


def test_chat_rejects_empty_text_without_attachments():
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": ""}]})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_web_search_falls_back_when_public_search_engines_fail(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "temporarily unavailable"

        def __init__(self, url):
            self.request = httpx.Request("GET", url)

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "search engine unavailable",
                request=self.request,
                response=httpx.Response(503, request=self.request, text=self.text),
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *args, **kwargs):
            return FakeResponse(url)

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)

    with pytest.raises(main.HTTPException) as error:
        await main.search_web("notícias de hoje")

    assert error.value.status_code == 502
    assert "Nenhum buscador retornou resultados" in error.value.detail


@pytest.mark.asyncio
async def test_web_search_uses_brave_when_configured(monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = '{"web":{"results":[{"title":"Notícias de hoje: comunicado oficial","url":"https://example.com/noticia","description":"Notícias de hoje com informações confirmadas"}]}}'
        url = "https://api.search.brave.com/res/v1/web/search"

        def json(self):
            return {
                "web": {
                    "results": [{
                        "title": "Notícias de hoje: comunicado oficial",
                        "url": "https://example.com/noticia",
                        "description": "Notícias de hoje com informações confirmadas",
                    }]
                }
            }

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *args, **kwargs):
            assert url == "https://api.search.brave.com/res/v1/web/search"
            assert kwargs["headers"]["X-Subscription-Token"] == "test-token"
            return FakeResponse()

    async def fake_read_page(client, source):
        return source

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(main, "_read_page", fake_read_page)

    results = await main.search_web("notícias de hoje")

    assert len(results) == 1
    assert results[0]["title"] == "Notícias de hoje: comunicado oficial"
    assert results[0]["url"] == "https://example.com/noticia"



@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("Quem ganhou a eleição presidencial?", "elections"),
        ("Quais são as últimas notícias de hoje?", "news"),
        ("Quais novidades de tecnologia foram lançadas?", "technology"),
        ("O que diz o estudo científico mais recente?", "science"),
        ("Como faço uma lista em Python?", "general"),
    ],
)
def test_research_engine_classifies_topics(question, topic):
    assert main.classify_research_topic(question) == topic


def test_research_query_expansion_keeps_original_question_and_adds_source_hints():
    query = main.build_search_query("Qual foi a última descoberta científica?")
    assert "Qual foi a última descoberta científica?" in query
    assert "artigo científico" in query
    assert "fonte primária" in query


def test_research_engine_rejects_dictionary_results_for_election_questions():
    item = {
        "title": "Significado da palavra ganhou",
        "url": "https://dictionary.example/ganhou",
        "snippet": "Definição e conjugação do verbo ganhar.",
    }
    assert not main.is_relevant_result("Quem ganhou a eleição presidencial?", item)


def test_research_engine_prioritizes_official_election_sources():
    official = {
        "title": "Resultado oficial da eleição presidencial",
        "url": "https://www.tse.jus.br/comunicacao/noticias/resultado-eleicao",
        "snippet": "O TSE publicou os votos válidos e o resultado eleitoral.",
    }
    generic = {
        "title": "Discussão sobre o resultado",
        "url": "https://example.org/discussao",
        "snippet": "Discussão sobre o resultado da eleição presidencial.",
    }
    ranked = main.rank_results("Quem ganhou a eleição presidencial?", [generic, official])
    assert ranked[0]["url"] == official["url"]
    assert len(ranked) == 2


def test_research_engine_deduplicates_urls_and_discards_unrelated_results():
    relevant = {
        "title": "Documentação oficial do Python",
        "url": "https://docs.python.org/3/tutorial/",
        "snippet": "Tutorial oficial da linguagem Python.",
    }
    unrelated = {
        "title": "Receitas de bolo",
        "url": "https://example.org/bolo",
        "snippet": "Receita de bolo de chocolate.",
    }
    ranked = main.rank_results("documentação oficial Python", [relevant, relevant, unrelated])
    assert len(ranked) == 1
    assert ranked[0]["url"] == relevant["url"]


@pytest.mark.parametrize(
    "question",
    [
        "Qual é a versão estável mais recente do Python?",
        "Qual a versão atual do Android?",
        "Qual foi uma descoberta científica recente?",
        "O que diz o estudo científico mais recente?",
        "Quais novidades de IA foram anunciadas recentemente?",
    ],
)
def test_requires_live_search_for_latest_technology_and_science(question):
    assert main.requires_live_search(question) is True


def test_news_intent_takes_priority_over_technology_topic():
    assert main.classify_research_topic("Quais são as notícias de IA de hoje?") == "news"


def test_latest_python_version_is_classified_as_technology():
    assert main.classify_research_topic("Qual é a versão estável mais recente do Python?") == "technology"


def test_recent_scientific_discovery_is_classified_as_science():
    assert main.classify_research_topic("Qual foi uma descoberta científica recente?") == "science"


def test_news_search_accepts_relevant_ai_headlines_with_synonyms():
    item = {
        "title": "AI companies announce new models today",
        "url": "https://example.org/ai-models",
        "snippet": "Latest artificial intelligence announcements and product releases.",
    }
    assert main.is_relevant_result("Quais são as notícias de IA de hoje?", item)


def test_news_intent_and_explicit_month_year_override_technology_classification():
    question = "Pesquise notícias sobre inteligência artificial no Brasil em novembro de 2026"
    assert main.classify_research_topic(question) == "news"
    assert main.has_explicit_date_filter(question) is True


def test_news_query_expansion_preserves_historical_period_without_recent_bias():
    question = "notícias sobre inteligência artificial em novembro de 2026"
    expanded = main.build_search_query(question)
    assert question in expanded
    assert "reportagens jornalísticas" in expanded
    assert "notícias atuais" not in expanded


def test_news_relevance_rejects_generic_intelligence_pages():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    unrelated = {
        "title": "15 tipos de inteligência: em quais você se destaca?",
        "url": "https://example.org/tipos-de-inteligencia",
        "snippet": "Conheça diferentes tipos de inteligência humana.",
    }
    assert not main.is_relevant_result(query, unrelated)


def test_news_relevance_requires_subject_even_on_trusted_news_domains():
    query = "notícias sobre inteligência artificial no Brasil"
    unrelated = {
        "title": "G1: resultado do campeonato brasileiro",
        "url": "https://g1.globo.com/esportes/noticia/resultado",
        "snippet": "Confira os resultados do futebol neste fim de semana.",
    }
    assert not main.is_relevant_result(query, unrelated)


def test_news_relevance_accepts_ai_reporting_from_a_news_source():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    relevant = {
        "title": "Empresas anunciam novidades em inteligência artificial no Brasil",
        "url": "https://g1.globo.com/tecnologia/noticia/ia",
        "snippet": "Reportagem de novembro de 2026 sobre novos sistemas de inteligência artificial no Brasil.",
    }
    assert main.is_relevant_result(query, relevant)



@pytest.mark.parametrize(
    "item",
    [
        {
            "title": "P+ Solution | Predict the Future",
            "url": "https://pesquisemais.com.br/",
            "snippet": "Soluções, Tecnologia e IA. Sobre nós, LGPD e Compliance.",
        },
        {
            "title": "Pesquisa - Microsoft Bing",
            "url": "https://www.bing.com/search",
            "snippet": "Pesquise com o Microsoft Bing e use o poder da IA.",
        },
        {
            "title": "Google Gemini",
            "url": "https://gemini.google.com/",
            "snippet": "Conheça o Gemini, o assistente de IA do Google.",
        },
        {
            "title": "15 tipos de inteligência",
            "url": "https://example.org/inteligencia",
            "snippet": "Conheça tipos de inteligência humana.",
        },
    ],
)
def test_ai_news_rejects_generic_sites_and_isolated_ai_acronym(item):
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    assert not main.is_relevant_result(query, item)


def test_ai_news_requires_explicit_country_and_requested_month():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    no_country = {
        "title": "Empresas anunciam novos modelos de inteligência artificial",
        "url": "https://example.org/noticia/ia",
        "snippet": "Reportagem de novembro de 2026 sobre novos modelos de inteligência artificial.",
    }
    wrong_period = {
        "title": "Empresas anunciam novos modelos de inteligência artificial no Brasil",
        "url": "https://example.org/noticia/ia",
        "snippet": "Reportagem de outubro de 2026 sobre novos modelos de inteligência artificial no Brasil.",
    }
    assert not main.is_relevant_result(query, no_country)
    assert not main.is_relevant_result(query, wrong_period)


def test_ai_news_accepts_contextual_ai_acronym_when_period_and_country_match():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    item = {
        "title": "Empresas anunciam novos modelos de IA generativa no Brasil",
        "url": "https://example.org/noticias/modelos-ia",
        "snippet": "Reportagem publicada em novembro de 2026 sobre modelos de IA generativa.",
    }
    assert main.is_relevant_result(query, item)


def test_ai_news_initial_candidate_can_wait_for_page_metadata():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    item = {
        "title": "Empresas anunciam novos modelos de inteligência artificial",
        "url": "https://example.org/noticia/ia",
        "snippet": "Reportagem sobre novos modelos de inteligência artificial.",
    }
    assert main.is_relevant_result(query, item, allow_incomplete_metadata=True)
    assert not main.is_relevant_result(query, item)


def test_rank_results_rejects_unverified_ai_news_metadata():
    query = "notícias sobre inteligência artificial no Brasil em novembro de 2026"
    item = {
        "title": "Empresas anunciam novidades em inteligência artificial",
        "url": "https://example.org/noticia/ia",
        "snippet": "Reportagem sobre novos sistemas de inteligência artificial.",
    }
    assert main.rank_results(query, [item]) == []


def test_bing_news_rss_redirect_url_is_decoded_to_original_destination():
    destination = "https://www.reuters.com/technology/artificial-intelligence/example/"
    bing_url = "https://www.bing.com/news/apiclick.aspx?url=" + main.quote(destination, safe="") + "&ref=FexRss"
    assert main._normalize_search_result_url(bing_url, "https://www.bing.com/news/search") == destination


def test_news_rss_parser_keeps_publisher_and_publication_date():
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><item>
      <title>Brasil anuncia nova política de inteligência artificial</title>
      <link>https://example.com/noticia/ia</link>
      <pubDate>Thu, 19 Nov 2026 13:24:00 GMT</pubDate>
      <source url="https://example.com">Exemplo Notícias</source>
      <description>Reportagem sobre inteligência artificial no Brasil.</description>
    </item></channel></rss>"""
    results = main._parse_news_rss(feed)
    assert len(results) == 1
    assert results[0]["title"].startswith("Brasil anuncia")
    assert "Veículo: Exemplo Notícias" in results[0]["snippet"]
    assert "Publicado em 2026-11-19" in results[0]["snippet"]


def test_bing_redirect_url_is_decoded_to_original_destination():
    destination = "https://www.reuters.com/technology/artificial-intelligence/example/"
    encoded = main.base64.urlsafe_b64encode(destination.encode()).decode().rstrip("=")
    bing_url = "https://www.bing.com/ck/a?u=a1" + encoded + "&ntb=1"
    assert main._normalize_search_result_url(bing_url, "https://www.bing.com/search") == destination


def test_bing_redirect_with_invalid_payload_is_not_treated_as_decoded_destination():
    bing_url = "https://www.bing.com/ck/a?u=a1%%%&ntb=1"
    normalized = main._normalize_search_result_url(bing_url, "https://www.bing.com/search")
    assert normalized.startswith("https://www.bing.com/ck/a?")


def test_extract_document_text_formats_csv_and_json():
    csv_text = main.extract_document_text("dados.csv", "text/csv", b"nome,valor\nAna,10\n")
    assert "nome | valor" in csv_text
    assert "Ana | 10" in csv_text

    json_text = main.extract_document_text("dados.json", "application/json", b'{"nome":"Ana","valor":10}')
    assert '"nome": "Ana"' in json_text
    assert '"valor": 10' in json_text


def test_extract_document_text_reads_docx_tables():
    from docx import Document
    from io import BytesIO

    document = Document()
    document.add_paragraph("Relatório de teste")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Item"
    table.cell(0, 1).text = "Valor"
    output = BytesIO()
    document.save(output)

    extracted = main.extract_document_text("relatorio.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", output.getvalue())
    assert "Relatório de teste" in extracted
    assert "Item | Valor" in extracted


def test_extract_document_text_reads_xlsx():
    from openpyxl import Workbook
    from io import BytesIO

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Vendas"
    sheet.append(["Produto", "Total"])
    sheet.append(["Livro", 25])
    output = BytesIO()
    workbook.save(output)

    extracted = main.extract_document_text("vendas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", output.getvalue())
    assert "[Planilha: Vendas]" in extracted
    assert "Produto | Total" in extracted
    assert "Livro | 25" in extracted


def test_research_engine_allows_results_for_short_explicit_queries():
    candidate = {
        "title": "Página inicial",
        "url": "https://example.org/",
        "snippet": "Informações gerais da página.",
    }
    ranked = main.rank_results("Oi", [candidate])
    assert len(ranked) == 1
    assert ranked[0]["url"] == candidate["url"]


def test_long_term_memory_only_captures_explicit_durable_context():
    from app.long_term_memory import extract_memory_candidate

    assert extract_memory_candidate("Meu projeto ADA-M usa Gemma 4 e Kokoro para conversar.") is not None
    assert extract_memory_candidate("Prefiro respostas diretas e instruções passo a passo.") is not None
    assert extract_memory_candidate("Qual é a melhor forma de organizar meu projeto?") is None
    assert extract_memory_candidate("Minha senha é exemplo-super-secreto-123.") is None


def test_long_term_memory_retrieval_is_contextual(monkeypatch):
    from app import long_term_memory

    monkeypatch.delenv("DATABASE_URL", raising=False)
    long_term_memory._VOLATILE.clear()
    long_term_memory.remember("test-owner", "Meu projeto ADA-M usa Gemma 4 e Kokoro.")
    long_term_memory.remember("test-owner", "Prefiro respostas diretas e instruções passo a passo.")

    related = long_term_memory.retrieve("test-owner", "Como está o projeto ADA-M?")
    assert any("ADA-M" in item for item in related)
    assert not any("Prefiro respostas" in item for item in related)
    assert long_term_memory.forget_all("test-owner") == 2


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('{"tool":"browser","args":{"action":"inspect"}}', ("browser", {"action": "inspect"})),
        ('{"tool":"browser","args":{"action":"click","index":2}}', ("browser", {"action": "click", "index": 2})),
        ('{"tool":"browser","args":{"action":"fill","index":3,"text":"hello"}}', ("browser", {"action": "fill", "index": 3, "text": "hello"})),
        ('{"tool":"browser","args":{"action":"hover","index":4}}', ("browser", {"action": "hover", "index": 4})),
        ('{"tool":"browser","args":{"action":"scroll","delta_y":900}}', ("browser", {"action": "scroll", "delta_y": 900})),
        ('{"tool":"browser","args":{"action":"scroll"}}', ("browser", {"action": "scroll", "delta_y": 700})),
    ],
)
def test_browser_tool_parser_accepts_inspection_and_indexed_actions(payload, expected):
    assert main.parse_tool_call(payload) == expected




def test_browser_tool_parser_rejects_invalid_scroll_distance_and_hover_target():
    assert main.parse_tool_call('{"tool":"browser","args":{"action":"scroll","delta_y":5000}}') is None
    assert main.parse_tool_call('{"tool":"browser","args":{"action":"scroll","delta_y":"down"}}') is None
    assert main.parse_tool_call('{"tool":"browser","args":{"action":"hover"}}') is None

def test_browser_tool_parser_rejects_unknown_actions():
    assert main.parse_tool_call('{"tool":"browser","args":{"action":"delete_all"}}') is None


def test_main_parser_accepts_isolated_terminal_tool():
    call = main.parse_tool_call(
        '{"tool":"terminal","args":{"command":"pwd && ls -la"}}'
    )
    assert call == ("terminal", {"command": "pwd && ls -la"})


def test_tool_call_output_budget_is_higher_than_previous_512_token_limit():
    assert main.TOOL_CALL_MAX_TOKENS == 4096


@pytest.mark.asyncio
async def test_browser_open_retries_transient_502(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self):
            if self._payload is None:
                raise ValueError("not json")
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            assert url == "https://browser.example/health"
            return FakeResponse(200, payload={"ok": "true", "service": "ada-m-browser", "browser": "ready"})

        async def post(self, *args, **kwargs):
            calls.append(kwargs["json"]["action"])
            assert kwargs["json"]["url"] == "https://example.com"
            if len(calls) == 1:
                return FakeResponse(502, text="<html>Bad Gateway</html>")
            return FakeResponse(200, payload={"ok": True, "title": "Example Domain", "text": "Example text"})

    async def no_sleep(_):
        return None

    monkeypatch.setattr(main, "BROWSER_SERVICE_ENABLED", True)
    monkeypatch.setattr(main, "BROWSER_SERVICE_URL", "https://browser.example")
    monkeypatch.setattr(main, "BROWSER_SERVICE_API_KEY", "test-key")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(main.asyncio, "sleep", no_sleep)

    result = await main.tool_browser_action("a" * 24, "open", url="https://example.com" + chr(0x2060))

    assert result["ok"] is True
    assert result["title"] == "Example Domain"
    assert calls == ["open", "open"]


@pytest.mark.asyncio
async def test_browser_does_not_retry_non_idempotent_click(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 502
        text = "<html>Bad Gateway</html>"

        def json(self):
            raise ValueError("not json")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            calls.append(kwargs["json"]["action"])
            return FakeResponse()

    monkeypatch.setattr(main, "BROWSER_SERVICE_ENABLED", True)
    monkeypatch.setattr(main, "BROWSER_SERVICE_URL", "https://browser.example")
    monkeypatch.setattr(main, "BROWSER_SERVICE_API_KEY", "test-key")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)

    result = await main.tool_browser_action("a" * 24, "click", selector="#submit")

    assert result["ok"] is False
    assert result["status_code"] == 502
    assert "Bad Gateway" in result["error"]
    assert calls == ["click"]


@pytest.mark.asyncio
async def test_web_fetch_retries_transient_502(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.headers = {"content-type": "text/html; charset=utf-8"}
            self.url = "https://example.com/"

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("GET", self.url)
                raise httpx.HTTPStatusError("upstream error", request=request,
                    response=httpx.Response(self.status_code, request=request, text=self.text))

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            calls.append(url)
            if len(calls) == 1:
                return FakeResponse(502, "Bad Gateway")
            return FakeResponse(200, "<html><body><p>Este é um conteúdo de teste suficientemente longo para extração.</p></body></html>")

    async def no_sleep(_):
        return None

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(main.asyncio, "sleep", no_sleep)

    result = await main.tool_web_fetch("https://example.com/")

    assert result["ok"] is True
    assert "conteúdo de teste" in result["text"]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_web_fetch_rejects_blocked_html_instead_of_returning_css(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '<html><head><title>Blocked</title><style>@font-face { font-family: "Roobert"; src: url("data:font/woff2;base64,AAAA"); }</style></head><body>Blocked</body></html>'
        headers = {"content-type": "text/html; charset=utf-8"}
        url = "https://example.com/"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)

    result = await main.tool_web_fetch("https://example.com/")

    assert result["ok"] is False
    assert result["blocked"] is True
    assert "bloqueio" in result["error"].lower()
    assert "@font-face" not in result["error"]
