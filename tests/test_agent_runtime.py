import pytest

from app.agent_runtime import (
    ToolDefinition,
    is_agent_task,
    is_browser_task,
    parse_tool_call,
    run_tool_loop,
)


def test_parse_valid_tool_call():
    tools = {"calculate": ToolDefinition("calculate", "math", ("expression",), lambda **kw: kw)}
    call = parse_tool_call('{"tool":"calculate","args":{"expression":"2+2"}}', tools)
    assert call is not None
    assert call.name == "calculate"
    assert call.arguments == {"expression": "2+2"}


@pytest.mark.parametrize("response", [
    '{"tool":"shell","args":{"command":"rm -rf /"}}',
    '{"tool":"calculate","args":[]}',
    '{"tool":"calculate","args":{}}',
    "not json",
])
def test_rejects_unknown_or_malformed_tool_calls(response):
    tools = {"calculate": ToolDefinition("calculate", "math", ("expression",), lambda **kw: kw)}
    assert parse_tool_call(response, tools) is None


def test_parses_fenced_json():
    tools = {"web_search"}
    call = parse_tool_call(chr(96) * 3 + 'json\n{"tool":"web_search","args":{"query":"ADA-M"}}\n' + chr(96) * 3, tools)
    assert call is not None and call.name == "web_search"


@pytest.mark.parametrize("message", [
    "Crie uma página de teste",
    "Corrija o erro do meu projeto",
    "Acesse o GitHub e analise o repositório",
    "Execute este script",
])
def test_detects_explicit_action_requests(message):
    assert is_agent_task(message)


@pytest.mark.parametrize("message", [
    "Como faço para criar uma página?",
    "O que é um navegador?",
    "Você consegue me ajudar?",
])
def test_does_not_treat_questions_as_execution_jobs(message):
    assert not is_agent_task(message)


@pytest.mark.asyncio
async def test_run_tool_loop_executes_only_registered_tools():
    calls = 0

    async def model(messages, tools_enabled):
        nonlocal calls
        calls += 1
        if calls == 1:
            return '{"tool":"calculate","args":{"expression":"2+2"}}'
        assert "Resultado da ferramenta" in messages[-1]["content"]
        return "O resultado é 4."

    tools = {
        "calculate": ToolDefinition(
            "calculate", "safe calculator", ("expression",),
            lambda expression: "4" if expression == "2+2" else "unsupported",
        )
    }
    result = await run_tool_loop([{"role": "user", "content": "calcule"}], model, tools)
    assert result == "O resultado é 4."
    assert calls == 2


def test_browser_tool_call_is_accepted_by_allowlist():
    tools = {"browser": ToolDefinition("browser", "isolated browser", ("action",), lambda **kw: kw)}
    call = parse_tool_call('{"tool":"browser","args":{"action":"open","url":"https://example.com"}}', tools)
    assert call is not None
    assert call.name == "browser"
    assert call.arguments["action"] == "open"


def test_browser_tool_call_still_requires_registered_tool():
    assert parse_tool_call('{"tool":"browser","args":{"action":"open"}}', {"calculate"}) is None


@pytest.mark.parametrize("message", [
    "https://example.com acesse pelo seu navegador e analise a página",
    "Abra https://example.com usando o Chromium",
    "Quero que você navegue pelo navegador até example.com",
    "Por favor, pelo seu navegador, visite https://example.com",
])
def test_detects_browser_intent_when_url_or_context_comes_first(message):
    assert is_browser_task(message)


@pytest.mark.parametrize("message", [
    "O que é um navegador?",
    "Como funciona o Chromium?",
    "Acesse este link",
    "Pesquise vulnerabilidades conhecidas de navegadores",
])
def test_browser_intent_requires_action_and_browser_reference(message):
    assert not is_browser_task(message)
