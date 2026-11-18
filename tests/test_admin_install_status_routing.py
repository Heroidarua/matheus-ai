import pytest

from app.agent_runtime import (
    extract_terminal_command,
    is_admin_install_tools_request,
    is_admin_install_tools_status_request,
)


@pytest.mark.parametrize("message", [
    'Execute exclusivamente o comando virtual "ada-admin install-tools-status" na VPS. '
    'Esta é uma consulta somente leitura. NÃO execute "ada-admin install-tools", '
    'não instale pacotes e não altere arquivos ou configurações. Retorne exatamente '
    "a saída da consulta, incluindo LoadState, ActiveState, SubState, Result, "
    "ExecMainStatus e ActiveEnterTimestamp.",
    "Consulte o estado da instalação administrativa de ferramentas na minha VPS. "
    "Não reinstale nada e não altere configurações.",
    "Execute ada-admin install-tools-status e depois ada-admin diagnostics. "
    "Não execute ada-admin install-tools.",
])
def test_install_status_request_never_routes_to_install(message):
    assert is_admin_install_tools_status_request(message)
    assert not is_admin_install_tools_request(message)
    assert extract_terminal_command(message) == "ada-admin install-tools-status"


@pytest.mark.parametrize("message", [
    "Instale o conjunto padrão de ferramentas Linux na VPS",
    "Prepare o kit de ferramentas do Ubuntu no servidor",
])
def test_explicit_install_requests_still_route_to_install(message):
    assert is_admin_install_tools_request(message)
    assert extract_terminal_command(message) == "ada-admin install-tools"


def test_explicit_diagnostics_request_stays_in_diagnostics_flow():
    message = (
        "ADA-M, execute ada-admin diagnostics na VPS conectada. Mostre o diagnóstico "
        "completo do servidor, incluindo hostname, uptime, memória, espaço em disco, "
        "estado dos serviços e disponibilidade das ferramentas. Não altere nenhuma configuração."
    )
    assert not is_admin_install_tools_status_request(message)
    assert not is_admin_install_tools_request(message)
    assert extract_terminal_command(message) == "ada-admin diagnostics"
