import pytest

from app.agent_runtime import (
    ToolDefinition,
    extract_terminal_command,
    is_agent_task,
    is_browser_task,
    is_terminal_task,
    normalize_tool_url,
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


@pytest.mark.parametrize("message", [
    "Use o terminal para executar pwd",
    "Abra o shell e rode python --version",
    "Instale as dependências pelo terminal",
])
def test_detects_terminal_intent(message):
    assert is_terminal_task(message)


@pytest.mark.parametrize("message", [
    "O que é um terminal Linux?",
    "Como funciona o shell?",
    "O terminal serve para quê?",
])
def test_terminal_intent_requires_an_execution_action(message):
    assert not is_terminal_task(message)



@pytest.mark.parametrize("message,expected", [
    ("Use seu terminal Linux: pwd && python3 --version", "pwd && python3 --version"),
    ("Execute no terminal \`git --version\`", "git --version"),
    ("Use o terminal e execute pwd", "pwd"),
    ("Use o terminal para executar:\\n\\```bash\\npwd && ls -la\\n\\```", "pwd && ls -la"),
])
def test_extracts_explicit_terminal_commands(message, expected):
    assert extract_terminal_command(message) == expected


@pytest.mark.parametrize("message", [
    "Use o terminal para verificar o ambiente",
    "O que é um terminal Linux?",
    "Execute uma tarefa no terminal sem especificar comando",
])
def test_does_not_invent_terminal_commands(message):
    assert extract_terminal_command(message) is None


def test_terminal_tool_call_is_accepted_by_allowlist():
    tools = {"terminal": ToolDefinition("terminal", "isolated shell", ("command",), lambda **kw: kw)}
    call = parse_tool_call('{"tool":"terminal","args":{"command":"pwd && ls -la"}}', tools)
    assert call is not None
    assert call.name == "terminal"
    assert call.arguments == {"command": "pwd && ls -la"}


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


@pytest.mark.parametrize("value,expected", [
    ("https://888game.app", "https://888game.app"),
    ("[https://888game.app](https://888game.app)", "https://888game.app"),
    ("[Abrir site](https://example.com/path)", "https://example.com/path"),
])
def test_normalize_tool_url_accepts_raw_and_markdown_links(value, expected):
    assert normalize_tool_url(value) == expected


def test_normalize_tool_url_rejects_non_string_values():
    assert normalize_tool_url(None) == ""

@pytest.mark.parametrize("response", [
    '<thinking>Vou abrir o site.</thinking>\n{"tool":"browser","args":{"action":"open","url":"https://sos01.com.br"}}',
    '```json\n{"tool":"browser","args":{"action":"open","url":"https://sos01.com.br"}}\n```',
    'A chamada é: {"tool":"browser","args":{"action":"open","url":"https://sos01.com.br"}}',
])
def test_parse_nested_browser_tool_json_with_wrappers(response):
    call = parse_tool_call(response, {"browser"})
    assert call is not None
    assert call.name == "browser"
    assert call.arguments == {"action": "open", "url": "https://sos01.com.br"}


def test_parse_tool_call_ignores_thinking_json_without_tool_call():
    response = '<thinking>{"analysis":"not a tool"}</thinking> Resposta normal.'
    assert parse_tool_call(response, {"browser"}) is None
