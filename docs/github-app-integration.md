# GitHub App da ADA-M

A integração usa uma GitHub App instalada apenas nos repositórios que o proprietário escolher. O backend guarda o ID da instalação na sessão assinada do navegador; não armazena Personal Access Tokens.

## Criar a GitHub App

1. Abra GitHub → Settings → Developer settings → GitHub Apps → New GitHub App.
2. Nome sugerido: **ADA-M GitHub**.
3. Homepage URL: `https://matheus-ai.onrender.com`.
4. Setup URL: `https://matheus-ai.onrender.com/api/github/callback`.
5. Em **Repository permissions**, configure:
   - **Contents: Read and write** — listar e ler arquivos, criar branches e gravar alterações na branch de trabalho.
   - **Pull requests: Read and write** — abrir Pull Requests para revisão.
   - **Metadata: Read-only** — permissão padrão obrigatória.
6. Não habilite permissões de administração, Actions, secrets, deployments ou webhooks. A versão atual não precisa delas.
7. Em **Where can this GitHub App be installed?**, selecione a opção que permita instalar na sua conta pessoal (ou nas organizações desejadas).
8. Crie a App. Copie o **App ID**, anote o **App slug** e gere uma **Private key** em Private keys → Generate a private key.
9. Instale a App na sua conta GitHub e selecione somente os repositórios que a ADA-M poderá acessar.

O fluxo usa a URL de instalação da GitHub App e valida o `installation_id` no callback. Não configure um Personal Access Token.

## Variáveis no Render

No serviço `matheus-ai` → Environment, adicione:

| Key | Value |
|---|---|
| `GITHUB_APP_ID` | App ID numérico da GitHub App |
| `GITHUB_APP_SLUG` | Slug da App, exibido na URL `github.com/apps/...` |
| `GITHUB_APP_PRIVATE_KEY` | Conteúdo integral do arquivo PEM gerado pelo GitHub |
| `GITHUB_SESSION_SECRET` | Segredo aleatório longo, exclusivo para assinar as sessões |
| `PUBLIC_APP_URL` | `https://matheus-ai.onrender.com` |
| `COOKIE_HTTPS_ONLY` | `true` |

A chave PEM pode ser colada com as linhas `BEGIN/END` e quebras de linha no campo de valor do Render. Nunca a coloque no GitHub, em commits, issues ou mensagens de chat. Se o painel não aceitar quebras de linha, use a mesma PEM com as quebras convertidas em `\\n`; o backend converte essa forma para quebras de linha antes de assinar o JWT.

Para `GITHUB_SESSION_SECRET`, gere um valor aleatório forte (por exemplo, 64 bytes em hexadecimal) fora do repositório. Não reutilize o App ID, a chave PEM ou a chave de outro serviço.

Após salvar, aguarde o deploy do Render.

## Configurar o callback

O campo **Setup URL** da GitHub App precisa apontar exatamente para:

`https://matheus-ai.onrender.com/api/github/callback`

O campo Homepage URL pode ser a URL principal da ADA-M. A integração atual usa o fluxo de instalação da GitHub App, portanto não precisa de OAuth user callback nem de webhooks.

## Como usar

1. Abra o menu **+ → Ferramentas → Conectar GitHub** na ADA-M.
2. Autorize a GitHub App e escolha os repositórios.
3. Selecione um repositório no painel GitHub.
4. No chat, peça à ADA-M para analisar o repositório ou informe um caminho como `app/main.py`. A integração injeta somente o contexto solicitado, em modo de leitura.
5. Para alterações, abra o painel GitHub, carregue o arquivo, edite/revise o conteúdo e gere uma prévia.
6. Confirme explicitamente para gravar em uma branch nova. A branch padrão (`main`) nunca é alvo de escrita.
7. Depois da gravação, use **Criar Pull Request** para abrir a revisão no GitHub.

## Segurança e limites atuais

- A instalação restringe os repositórios acessíveis; o backend confere a seleção contra a lista de repositórios da instalação.
- Tokens de instalação são curtos e emitidos sob demanda; a chave privada permanece apenas nas variáveis do Render.
- Leitura pelo chat é somente sob demanda, quando a mensagem menciona explicitamente GitHub, repositório, arquivo, branch, commit, issue ou Pull Request.
- Escritas exigem duas ações humanas distintas: confirmar a gravação na branch e, separadamente, criar o Pull Request.
- O conteúdo dos repositórios é tratado como dado não confiável, não como instrução para a ADA-M.
- As prévias de alteração expiram em 15 minutos e ficam temporariamente na memória do processo. Se o serviço reiniciar antes da confirmação, será necessário gerar a prévia novamente.
- A primeira versão lista até 100 repositórios por instalação e até 20 arquivos por proposta. O painel permite revisar um arquivo por proposta.
- O merge do Pull Request continua sendo uma decisão do usuário no GitHub.
