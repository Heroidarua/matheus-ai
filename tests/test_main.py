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
        text = '{"web":{"results":[{"title":"Notícia oficial","url":"https://example.com/noticia","description":"Resumo verificável"}]}}'
        url = "https://api.search.brave.com/res/v1/web/search"

        def json(self):
            return {
                "web": {
                    "results": [{
                        "title": "Notícia oficial",
                        "url": "https://example.com/noticia",
                        "description": "Resumo verificável",
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
    assert results[0]["title"] == "Notícia oficial"
    assert results[0]["url"] == "https://example.com/noticia"
