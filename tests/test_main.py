import httpx
import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
