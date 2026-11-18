import pytest

from app.agent_runtime import (
    ToolDefinition,
    extract_terminal_command,
    is_agent_task,
    is_admin_install_tools_request,
    is_admin_diagnostics_request,
    is_admin_install_tools_status_request,
    is_security_audit_request,
    is_browser_task,
    is_terminal_task,
    normalize_tool_url,
    parse_tool_call,
    run_tool_loop,
    should_run_agent_loop,
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
    "Instale o conjunto padrão de ferramentas Linux na VPS",
    "ADA-M, instalar as ferramentas padrão no servidor",
    "Prepare o kit de ferramentas do Ubuntu na VPS",
    "ADA-M, baixe suas próprias ferramentas de hacking",
    "Baixe as ferramentas de pentest da ADA-M",
    "Instale ferramentas de auditoria de segurança na minha VPS",
])
def test_admin_install_intent_routes_to_fixed_virtual_command(message):
    assert is_admin_install_tools_request(message)
    assert extract_terminal_command(message) == "ada-admin install-tools"


@pytest.mark.parametrize("message", [
    "Quais ferramentas Linux você recomenda?",
    "Como instalar ferramentas no meu computador?",
    "Instale o pacote solicitado no projeto",
    "Quais ferramentas de hacking existem?",
    "Como baixar ferramentas de pentest?",
])
def test_admin_install_intent_does_not_match_unrelated_requests(message):
    assert not is_admin_install_tools_request(message)



@pytest.mark.parametrize("message", [
    "Estou tentando hackear meu site",
    "Quero fazer um pentest no meu domínio",
    "Faça um teste de segurança no meu servidor",
])
def test_detects_security_audit_requests(message):
    assert is_security_audit_request(message)


@pytest.mark.parametrize("message", [
    "Estou tentando hackear meu site",
    "Quero fazer um pentest no meu domínio",
    "Faça uma auditoria de segurança, tenho autorização para o servidor",
])
def test_authorized_security_audit_requests_require_explicit_ownership(message):
    assert is_terminal_task(message)


@pytest.mark.parametrize("message", [
    "Quero hackear o site example.com",
    "Faça um pentest no servidor do cliente",
])
def test_security_audit_without_explicit_authorization_does_not_auto_run(message):
    assert is_security_audit_request(message)
    assert not is_terminal_task(message)


@pytest.mark.parametrize("message,expected", [
    ("pwd && python3 --version && node --version && git --version", "pwd && python3 --version && node --version && git --version"),
    ("git --version", "git --version"),
    (chr(96) * 3 + "bash" + chr(10) + "pwd && ls -la" + chr(10) + chr(96) * 3, "pwd && ls -la"),
])
def test_detects_and_extracts_raw_shell_commands(message, expected):
    assert is_terminal_task(message)
    assert extract_terminal_command(message) == expected

@pytest.mark.parametrize("message", [
    "O que é um terminal Linux?",
    "Como funciona o shell?",
    "O terminal serve para quê?",
])
def test_terminal_intent_requires_an_execution_action(message):
    assert not is_terminal_task(message)



@pytest.mark.parametrize("message,expected", [
    ("Use seu terminal Linux: pwd && python3 --version", "pwd && python3 --version"),
    ("Execute no terminal `git --version`", "git --version"),
    ("Use o terminal e execute pwd", "pwd"),
    ("Use o terminal para executar:\n```bash\npwd && ls -la\n```", "pwd && ls -la"),
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



@pytest.mark.asyncio
async def test_run_tool_loop_supports_multiple_terminal_steps():
    executed = []

    async def model(messages, tools_enabled):
        if not executed:
            return '{"tool":"terminal","args":{"command":"pwd"}}'
        if len(executed) == 1:
            assert "ada-runner/workspace" in messages[-1]["content"]
            return '{"tool":"terminal","args":{"command":"python3 --version"}}'
        assert "Python 3." in messages[-1]["content"]
        return "Projeto verificado com sucesso."

    async def terminal(command):
        executed.append(command)
        if command == "pwd":
            return {"stdout": "/home/ada-runner/workspace", "exit_code": 0}
        return {"stdout": "Python 3.12.3", "exit_code": 0}

    tools = {
        "terminal": ToolDefinition(
            "terminal", "restricted Linux terminal", ("command",), terminal
        )
    }
    result = await run_tool_loop(
        [{"role": "user", "content": "Crie e teste um projeto"}],
        model,
        tools,
        max_steps=4,
    )
    assert result == "Projeto verificado com sucesso."
    assert executed == ["pwd", "python3 --version"]



@pytest.mark.parametrize(
    "agent_mode,summary,codegen,terminal_task,terminal_ready,search,search_failed,expected",
    [
        (True, False, True, False, True, False, False, True),
        (True, False, True, False, False, False, False, False),
        (False, False, True, False, True, False, False, False),
        (True, True, False, False, True, False, False, False),
        (False, False, False, False, False, True, False, True),
        (False, False, False, False, False, True, True, False),
    ],
)
def test_agent_loop_activation_for_coding_and_search(
    agent_mode, summary, codegen, terminal_task, terminal_ready, search, search_failed, expected
):
    assert should_run_agent_loop(
        agent_mode_active=agent_mode,
        summary_requested=summary,
        code_generation_needed=codegen,
        terminal_task=terminal_task,
        terminal_configured=terminal_ready,
        should_search=search,
        search_unavailable=search_failed,
    ) is expected



def test_file_creation_request_requires_terminal_when_agent_and_executor_are_ready():
    from app.agent_runtime import requires_terminal_execution

    prompt = (
        "Crie uma pasta chamada validacao_relatorio. Dentro dela, crie calculadora.py, "
        "test_calculadora.py com unittest e README.md. Execute os testes."
    )
    assert requires_terminal_execution(
        prompt,
        agent_mode_active=True,
        terminal_configured=True,
    )


def test_file_creation_request_does_not_require_terminal_when_executor_is_unavailable():
    from app.agent_runtime import requires_terminal_execution

    assert not requires_terminal_execution(
        "Crie uma pasta e um arquivo README.md",
        agent_mode_active=True,
        terminal_configured=False,
    )


def test_browser_task_keeps_browser_priority_over_implicit_terminal():
    from app.agent_runtime import requires_terminal_execution

    assert not requires_terminal_execution(
        "Acesse um site pelo navegador e analise os botões",
        agent_mode_active=True,
        terminal_configured=True,
        browser_task=True,
    )


def test_explicit_terminal_task_reports_unavailable_executor_instead_of_skipping():
    from app.agent_runtime import requires_terminal_execution

    assert requires_terminal_execution(
        "Use o terminal para executar pwd",
        agent_mode_active=True,
        terminal_configured=False,
        explicit_terminal_task=True,
    )



def test_detects_truncated_tool_call_attempts_without_executing_them():
    from app.agent_runtime import looks_like_tool_call

    assert looks_like_tool_call('{"tool":"terminal","args":{"command":"cat << EOF')
    assert looks_like_tool_call('prefix {"tool": "browser", "args":')
    assert not looks_like_tool_call('{"analysis":"not a tool call"}')
    assert not looks_like_tool_call('Resposta normal sem ferramenta.')



@pytest.mark.parametrize("command", [
    "nmap -sV --top-ports 20 192.0.2.10",
    "sqlmap -u https://example.invalid/item?id=1 --batch --risk=1 --level=1",
    "nikto -h https://example.invalid",
    "gobuster dir -u https://example.invalid -w /tmp/wordlist",
    "jq --version",
    "nc -vz 192.0.2.10 443",
])
def test_installed_audit_tools_are_recognized_as_terminal_commands(command):
    assert is_terminal_task(command)
    assert extract_terminal_command(command) == command


def test_agent_prompt_documents_installed_tools_and_authorization_boundaries():
    from app.agent_runtime import AGENT_TOOLS_SPEC

    for tool in ("nmap", "sqlmap", "nikto", "gobuster", "jq", "netcat"):
        assert tool in AGENT_TOOLS_SPEC
    assert "autorização explícita" in AGENT_TOOLS_SPEC
    assert "Nunca faça varredura ampla da internet" in AGENT_TOOLS_SPEC


def test_agent_prompt_checks_binaries_on_remote_executor():
    from app.agent_runtime import AGENT_TOOLS_SPEC

    assert "command -v nmap sqlmap nikto gobuster jq nc" in AGENT_TOOLS_SPEC
    assert "não presuma que instalar pacotes no Dockerfile da API os instalou na VPS" in AGENT_TOOLS_SPEC


@pytest.mark.asyncio
async def test_run_tool_loop_can_execute_more_than_ten_steps():
    executed = []

    async def model(messages, tools_enabled):
        if len(executed) < 12:
            return '{"tool":"terminal","args":{"command":"printf step"}}'
        return "Tarefa concluída após 12 execuções."

    async def terminal(command):
        executed.append(command)
        return {"stdout": f"step {len(executed)}", "exit_code": 0}

    tools = {
        "terminal": ToolDefinition(
            "terminal", "restricted Linux terminal", ("command",), terminal
        )
    }
    result = await run_tool_loop(
        [{"role": "user", "content": "Execute doze etapas"}],
        model,
        tools,
    )
    assert result == "Tarefa concluída após 12 execuções."
    assert len(executed) == 12


def test_agent_prompt_no_longer_imposes_six_or_twenty_four_call_caps():
    from app.agent_runtime import AGENT_TOOLS_SPEC

    assert "Não imponha teto acumulado de chamadas de terminal por tarefa" in AGENT_TOOLS_SPEC
    assert "até 6 chamadas" not in AGENT_TOOLS_SPEC
    assert "24 chamadas acumuladas" not in AGENT_TOOLS_SPEC


@pytest.mark.parametrize("command", [
    "ada-admin diagnostics",
    "ada-admin install-tools-status",
    "ada-admin install-tools",
])
def test_fixed_vps_admin_commands_are_recognized_as_terminal_tasks(command):
    assert is_terminal_task(command)
    assert extract_terminal_command(command) == command


def test_vps_diagnostics_request_requires_terminal_in_agent_mode():
    from app.agent_runtime import requires_terminal_execution

    assert requires_terminal_execution(
        "Verifique o estado da minha VPS e os serviços ADA-M",
        agent_mode_active=True,
        terminal_configured=True,
    )


@pytest.mark.parametrize("message,expected", [
    (
        "ADA-M, execute ada-admin diagnostics na VPS conectada. Mostre o diagnóstico completo do servidor, incluindo hostname, uptime, memória, espaço em disco, estado dos serviços e disponibilidade das ferramentas. Não altere nenhuma configuração.",
        "ada-admin diagnostics",
    ),
    (
        "ADA-M, verifique o estado da minha VPS e mostre o diagnóstico do servidor.",
        "ada-admin diagnostics",
    ),
    (
        "ADA-M, execute ada-admin install-tools-status e mostre o resultado da instalação na VPS.",
        "ada-admin install-tools-status",
    ),
])
def test_natural_language_vps_readonly_admin_requests_route_deterministically(message, expected):
    if expected == "ada-admin diagnostics":
        assert is_admin_diagnostics_request(message)
    else:
        assert is_admin_install_tools_status_request(message)
    assert is_terminal_task(message)
    assert extract_terminal_command(message) == expected


@pytest.mark.parametrize("message", [
    "Como funciona o diagnóstico de uma VPS?",
    "Quais ferramentas devo instalar no servidor?",
    "O que significa status de instalação?",
])
def test_admin_readonly_natural_language_detection_does_not_match_questions(message):
    assert not is_admin_diagnostics_request(message)
    assert not is_admin_install_tools_status_request(message)
