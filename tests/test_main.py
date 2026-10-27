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


def test_chat_rejects_empty_text_without_attachments():
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": ""}]})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_web_search_reports_missing_brave_key(monkeypatch):
    monkeypatch.setattr(main, "BRAVE_SEARCH_API_KEY", "")
    with pytest.raises(main.HTTPException) as error:
        await main.search_web("teste")
    assert error.value.status_code == 503
