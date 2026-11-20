# ADA-M Browser Service

Serviço Chromium/Playwright separado da API principal. Ele não altera nem substitui o Gemma 4:31B e não executa comandos de shell.

## Deploy separado no Render

1. No Render, crie um **New + → Web Service** usando o mesmo repositório `Heroidarua/matheus-ai`.
2. Selecione o runtime **Docker**.
3. Defina **Root Directory** como `browser-service` (assim o Render usará `browser-service/Dockerfile`).
4. Configure `ADA_BROWSER_API_KEY` com uma chave aleatória longa (32 bytes ou mais). Não reutilize a chave do modelo nem a `APP_API_KEY`.
5. Opcional: configure `BROWSER_MAX_SESSIONS=1`, `BROWSER_MAX_TABS=1`, `BROWSER_SESSION_TTL=1800`. Os padrões agora são uma sessão e uma aba para reduzir picos de RAM e reinicializações do Chromium em instâncias pequenas; aumente somente se o plano tiver memória suficiente.
6. Configure o Health Check Path como `/health` e faça deploy. A rota deve responder com `ok=true`. O padrão é uma sessão simultânea para reduzir o consumo de RAM; aumente esse limite somente se a instância tiver memória suficiente.
7. Na API ADA-M principal, configure `BROWSER_SERVICE_URL` com a URL HTTPS desse serviço e `BROWSER_SERVICE_API_KEY` com exatamente a mesma chave `ADA_BROWSER_API_KEY`.
8. Faça o redeploy da API principal depois de configurar as duas variáveis.

## Render Free e inicialização após inatividade

Quando o serviço fica suspenso por inatividade no plano gratuito, a API principal da ADA-M
faz uma verificação autenticada? Não: `/health` é uma rota pública de saúde e é consultada
antes de cada nova navegação para despertar a instância. A API aguarda até o Chromium informar
`browser=ready`, com tentativas e pausas progressivas, antes de enviar a ação `open`.
Se o serviço não acordar dentro da janela de espera, a ADA-M retorna uma mensagem clara para
tentar novamente, em vez de tratar a hibernação como falha definitiva. Ações externas como
`click` não são repetidas automaticamente.

## API interna

Todas as ações (exceto `/health`) exigem `X-ADA-Browser-Key`. Use `POST /v1/action` com JSON:

```json
{"session_id":"opaque-session-id-with-at-least-20-chars","action":"open","url":"https://example.com"}
```

Ações: `open`, `inspect` (lista links, botões e campos visíveis), `click`, `hover`, `scroll` (rolagem vertical limitada a 3.000 px por ação), `fill`, `select`, `press`, `text`, `screenshot`, `tabs`, `new_tab`, `close_tab`, `back`, `forward`, `refresh`, `close`.

Cada sessão recebe contexto Chromium isolado, uma aba por padrão e expiração por inatividade. URLs precisam usar HTTP(S) público; localhost, redes privadas, IPs não globais, hostnames locais e portas fora da allowlist são bloqueados. Downloads são desativados. Conteúdo de páginas deve ser tratado pela ADA-M como dado externo não confiável.

## Limites importantes

- Sessões ficam em memória e são encerradas quando o serviço reinicia ou entra em sleep.
- O serviço é stateless no disco; cookies e logins não são persistidos entre reinicializações.
- Não há acesso a arquivos locais, shell, extensões, pagamentos ou envio automático de formulários sensíveis.
- A ADA-M deve pedir confirmação antes de ações externas irreversíveis (compras, pagamentos, envio/publicação, exclusão ou mudanças de conta).
