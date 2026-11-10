import pytest

from app.main import is_programming_request


@pytest.mark.parametrize(
    ("mode", "message", "expected"),
    [
        ("programador", "Olá, tudo bem?", True),
        ("normal", "Crie uma API em Python com FastAPI", True),
        ("normal", "Corrija esse bug no JavaScript", True),
        ("normal", "Explique a diferença entre HTML e CSS", True),
        ("normal", "Qual é a previsão do tempo amanhã?", False),
        ("normal", "Conte uma história sobre um dragão", False),
        ("livre", "Analise este repositório e o código", True),
    ],
)
def test_programming_request_detection(mode, message, expected):
    assert is_programming_request(mode, message) is expected
