# ADA-M — plano de autonomia (fase 1)

## Objetivo

Adicionar uma base de agente que permita ao Gemma 4:31B escolher ferramentas registradas, receber seus resultados e continuar o planejamento em um ciclo limitado. O modelo principal e a configuração do provedor não são alterados.

## O que esta fase entrega

- Protocolo JSON para chamadas de ferramentas.
- Lista de ferramentas permitidas (allowlist); ferramentas desconhecidas ou argumentos inválidos são rejeitados.
- Orquestrador assíncrono reutilizável com limite de etapas, tratamento de erros e retorno final do modelo.
- Detecção conservadora de pedidos explícitos de execução.
- Instruções para o agente não alegar ações que ainda não estão integradas.
- Testes unitários do parser, detecção de intenção e ciclo de execução.

## Limites deliberados

Esta fase não instala Chromium, não cria um navegador gráfico, não fornece shell ao modelo e não concede acesso irrestrito a arquivos, contas ou rede. O executor Python legado não é promovido a ferramenta universal. As próximas fases devem conectar serviços isolados (Playwright/Chromium, executor de código em container e adaptadores GitHub/arquivos) à allowlist, com autenticação, autorização por usuário, limites de recursos e auditoria.

## Próximas fases

1. Conectar o ciclo ao endpoint de chat e expor estados de execução na interface.
2. Criar o serviço independente de navegador Chromium + Playwright.
3. Criar executor isolado com limites de CPU, memória, tempo, filesystem e rede.
4. Integrar GitHub, biblioteca de arquivos e APIs com escopos mínimos.
5. Adicionar tarefas persistentes, retomada, cancelamento e trilha de auditoria.

## Configuração

Nenhuma variável de ambiente nova é exigida nesta fase. A configuração atual do Gemma 4:31B permanece intacta.
