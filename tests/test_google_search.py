import httpx
import pytest

from app.google_search import _extract_grounded_output, google_grounded_search


def test_extract_grounded_output_reads_google_search_grounding_metadata():
    payload = {
        "candidates": [{
            "content": {"parts": [{"text": "O TSE publicou o resultado oficial."}]},
            "groundingMetadata": {
                "groundingChunks": [
                    {"web": {"title": "TSE", "uri": "https://www.tse.jus.br/resultado"}},
                    {"web": {"title": "Invalid", "uri": "javascript:alert(1)"}},
                ],
                "groundingSupports": [{
                    "groundingChunkIndices": [0],
                    "segment": {"text": "O resultado foi publicado pelo TSE."},
                }],
            },
        }]
    }
    summary, sources = _extract_grounded_output(payload)
    assert "resultado oficial" in summary
    assert len(sources) == 1
    assert sources[0]["title"] == "TSE"
    assert sources[0]["url"] == "https://www.tse.jus.br/resultado"
    assert "publicado pelo TSE" in sources[0]["snippet"]


def test_extract_grounded_output_handles_empty_payload():
    assert _extract_grounded_output({}) == ("", [])


def test_extract_grounded_output_deduplicates_urls():
    payload = {
        "candidates": [{
            "content": {"parts": [{"text": "Síntese."}]},
            "groundingMetadata": {
                "groundingChunks": [
                    {"web": {"title": "Fonte A", "uri": "https://example.org/a"}},
                    {"web": {"title": "Fonte A duplicada", "uri": "https://example.org/a"}},
                ]
            },
        }]
    }
    _, sources = _extract_grounded_output(payload)
    assert len(sources) == 1


@pytest.mark.asyncio
async def test_google_grounded_search_uses_generate_content_and_search_tool(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": "Resultado confirmado."}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"title": "TSE", "uri": "https://www.tse.jus.br/"}},
                        ]
                    },
                }]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            assert "models/gemini-2.5-flash:generateContent" in url
            assert kwargs["params"]["key"] == "test-key"
            assert kwargs["json"]["tools"] == [{"google_search": {}}]
            return FakeResponse()

    monkeypatch.setattr("app.google_search.httpx.AsyncClient", FakeClient)
    summary, sources = await google_grounded_search("Quem ganhou a eleição?", api_key="test-key")
    assert summary == "Resultado confirmado."
    assert sources[0]["title"] == "TSE"


@pytest.mark.asyncio
async def test_google_grounded_search_falls_back_when_configured_model_is_invalid(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status):
            self.status = status
            self.request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")

        def raise_for_status(self):
            if self.status >= 400:
                raise httpx.HTTPStatusError(
                    "model unavailable",
                    request=self.request,
                    response=httpx.Response(self.status, request=self.request),
                )

        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": "Found it."}]},
                    "groundingMetadata": {
                        "groundingChunks": [{"web": {"title": "Official", "uri": "https://example.org"}}]
                    },
                }]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            if "not-a-real-model" in url:
                return FakeResponse(404)
            return FakeResponse(200)

    monkeypatch.setattr("app.google_search.httpx.AsyncClient", FakeClient)
    summary, sources = await google_grounded_search(
        "current news", api_key="test-key", model="not-a-real-model"
    )
    assert len(calls) == 2
    assert "gemini-2.5-flash:generateContent" in calls[1]
    assert summary == "Found it."
    assert len(sources) == 1
