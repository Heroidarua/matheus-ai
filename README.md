# Matheus AI

Assistente pessoal independente para conversas gerais, escrita, estudos, tecnologia e ajuda prática. O projeto combina um modelo de linguagem configurável com uma base de conhecimento própria.

## Personalização com seus dados

O projeto agora suporta **RAG (busca e recuperação de conhecimento)**: antes de responder, o backend procura trechos relevantes nos arquivos Markdown e TXT de `data/knowledge/` e inclui os trechos selecionados no contexto do modelo.

Isso personaliza as respostas com informações do projeto sem retreinar os pesos do modelo. O sistema de busca é lexical e leve, feito com a biblioteca padrão do Python; não precisa de banco vetorial nem de outra API. A qualidade depende do modelo configurado e de como os documentos são escritos.

### Conteúdo especializado disponível

A base inicial inclui guias curados para:
- Python, engenharia de software e testes.
- Linux, Android, Termux e PRoot.
- Desenvolvimento web, APIs e segurança defensiva.
- Pesquisa, avaliação de evidências e verificação de fontes.
- Automação, integrações, deploy e observabilidade.

Consulte `data/knowledge/indice-e-curadoria.md` para o catálogo, critérios de qualidade e limitações. Os documentos registram links de fontes primárias e uma data de revisão. O mecanismo atual continua sendo RAG lexical: ele recupera trechos por palavras relacionadas, mas não faz fine-tuning nem valida automaticamente se uma fonte mudou.

### Como adicionar conhecimento

1. Crie um arquivo `.md` ou `.txt` dentro de `data/knowledge/`.
2. Organize o conteúdo em parágrafos com títulos claros e fatos objetivos.
3. Faça commit dos arquivos no repositório privado e aguarde o deploy do Render.
4. Consulte `/api/knowledge/status` para ver apenas a quantidade e o tamanho total dos documentos carregados. Esse endpoint não devolve o conteúdo dos arquivos.
5. Faça uma pergunta no chat que corresponda ao conteúdo inserido.

Limites atuais: até 100 arquivos elegíveis, cada um com até 1 MB; até quatro trechos são recuperados por pergunta. Arquivos maiores são ignorados. A busca considera apenas arquivos `.md` e `.txt`.

**Privacidade:** não adicione senhas, tokens, documentos de identidade, dados bancários ou informações de terceiros sem autorização. Se o Render estiver hospedando o chat, os trechos recuperados são enviados ao provedor de modelo configurado para gerar a resposta. Use somente dados que você aceita compartilhar com esse provedor. A base no repositório é distribuída junto com a imagem do serviço; mantenha o repositório privado se os documentos forem privados.

## Recursos

- Interface de chat responsiva em português.
- Upload de imagens JPG, PNG e WebP para análise visual (o modelo/provedor precisa oferecer visão).
- Anexos de PDF com extração de texto e arquivos de texto/código comuns, até 5 MB por arquivo.
- Backend FastAPI com endpoint `/api/chat`.
- Compatibilidade com APIs de chat no formato OpenAI.
- Personalização por prompt e recuperação de conhecimento local (RAG).
- Ferramentas locais limitadas a cálculos aritméticos e horário UTC.
- Endpoint `/api/knowledge/status` para métricas da base, sem expor documentos.
- Preparado para deploy web no Render.

## Biblioteca persistente de arquivos

Além dos guias versionados em `data/knowledge/`, a ADA-M oferece uma biblioteca privada de documentos com PostgreSQL. O usuário pode enviar PDF, DOCX, XLSX/XLSM, TXT, MD, CSV e JSON pela opção **+ → Ferramentas → Biblioteca de arquivos**. A interface permite listar, pesquisar e excluir documentos.

O backend extrai texto sem executar arquivos, calcula SHA-256 para evitar duplicatas e guarda texto/metadados em uma tabela própria. Durante as conversas, trechos relevantes do acervo são recuperados e combinados com a base curada. A busca atual é lexical, não vetorial; os documentos não treinam nem alteram os pesos do modelo.

**Configuração obrigatória:** configure `DATABASE_URL` no Render apontando para um PostgreSQL persistente. O blueprint declara a variável, mas não cria o banco. Sem ela, a biblioteca fica indisponível e o restante do chat/pesquisa continua operando. Consulte [docs/biblioteca-de-arquivos.md](docs/biblioteca-de-arquivos.md) para formatos, limites, endpoints e requisitos de acesso seguro. PDFs digitalizados ainda precisam de OCR.

## Isso é um modelo treinado?

Ainda não. RAG fornece documentos relevantes ao modelo durante a conversa, mas não altera os pesos nem cria conhecimento permanente dentro do próprio modelo. Para um ajuste fino (fine-tuning) real, será necessário preparar exemplos de treinamento de qualidade, escolher uma licença/modelo compatível e executar o treinamento em hardware ou serviço adequado. A pasta `data/training/` descreve o formato inicial esperado; nenhum treinamento é executado automaticamente pelo Render.

## Requisitos

- Python 3.11+
- Um endpoint de modelo compatível com a API OpenAI (local ou hospedado)

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abra http://localhost:8000.

Configure no `.env`:
- `MODEL_BASE_URL`: URL base do endpoint compatível com OpenAI. Para Ollama local, use `http://localhost:11434/v1`.
- `MODEL_NAME`: nome do modelo instalado/disponível no endpoint.
- `OPENAI_API_KEY`: chave exigida pelo provedor; para Ollama local, normalmente pode ser `ollama`.
- `KNOWLEDGE_DIR`: pasta da base de conhecimento; por padrão, `data/knowledge`.
- `APP_API_KEY`: opcional; se definida, exige o cabeçalho `X-App-Key` nas chamadas à API.

## Deploy no Render

O blueprint `render.yaml` cria somente o serviço web. **Ele não hospeda automaticamente os pesos do modelo nem faz fine-tuning.** Configure um endpoint de modelo acessível pela internet em `MODEL_BASE_URL`, o nome em `MODEL_NAME` e os segredos nas variáveis de ambiente do Render. Não coloque chaves no código nem no repositório. Os arquivos de `data/knowledge/` são copiados para a imagem durante o build.

### Pesquisa Google em tempo real mantendo o modelo atual

O ADA-M pode usar **Google Search Grounding** como provedor de pesquisa, sem trocar o modelo que escreve a resposta final. O Gemini é chamado apenas para pesquisar na web e devolver uma síntese auxiliar com citações; o backend continua enviando as evidências ao modelo definido em `MODEL_BASE_URL` e `MODEL_NAME`. Se o Google falhar ou não devolver citações, o sistema continua tentando Brave, SearXNG (se configurado), DuckDuckGo e Bing.

1. Crie uma chave no [Google AI Studio](https://aistudio.google.com/app/apikey).
2. No Render, abra **Environment** e configure:
   - `GOOGLE_GEMINI_API_KEY`: sua chave, mantida somente no servidor.
   - `GOOGLE_SEARCH_MODEL`: `gemini-3.8-flash` (opcional; pode ser ajustado para um modelo que suporte Google Search Grounding).
3. Salve e aguarde o deploy. Ative **Pesquisar na web** no chat ou faça uma pergunta atual que acione a pesquisa automática.
4. Consulte os logs do Render procurando `Google Search Grounding: citations=` para confirmar que a API retornou citações.

**Custos e privacidade:** a pesquisa usa a Gemini API e pode consumir cota ou gerar cobrança. A documentação atual descreve cobrança por consulta de pesquisa para modelos Gemini 3+, com uma franquia que pode mudar; confira [preços oficiais](https://ai.google.dev/gemini-api/docs/pricing) antes de uso contínuo. A pergunta é enviada ao Google. Nunca coloque a chave no frontend, em mensagens ou em commits. A pesquisa Google é independente do provedor de resposta principal.

**Limite desta etapa:** Gmail, Drive, Calendar, Docs e Sheets exigem OAuth consentido por cada usuário, escopos específicos e armazenamento seguro de tokens no servidor. Não são ativados automaticamente por uma chave de pesquisa; não conceda permissões de Workspace até que esse fluxo seja configurado e testado.

### Integração Google Workspace (Gmail, Drive, Calendar, Docs e Sheets)

O módulo `app/google_workspace.py` adiciona autorização OAuth no servidor e endpoints de leitura. Ele fica **desativado por padrão** até todas as credenciais abaixo estarem configuradas. Não muda o modelo principal nem a pesquisa Google.

#### Configuração necessária

1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/).
2. Ative Gmail API, Google Drive API, Google Calendar API, Google Docs API e Google Sheets API.
3. Configure a tela de consentimento OAuth e crie um cliente OAuth do tipo **Aplicativo da Web**.
4. Adicione exatamente `https://SEU-SERVICO.onrender.com/api/google/callback` em **Authorized redirect URIs** (use a URL real do serviço).
5. No Render, crie um banco PostgreSQL e copie a URL interna/privada como `DATABASE_URL`. Não use a URL pública se a aplicação estiver no mesmo ambiente privado.
6. Configure no Render:
   - `GOOGLE_OAUTH_CLIENT_ID`: ID do cliente OAuth.
   - `GOOGLE_OAUTH_CLIENT_SECRET`: segredo OAuth.
   - `DATABASE_URL`: URL privada do PostgreSQL.
   - `GOOGLE_TOKEN_ENCRYPTION_KEY`: chave Fernet criada uma única vez com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   - `PUBLIC_APP_URL`: URL HTTPS pública real, sem barra final.
7. Faça deploy. Abra `/api/google/status`; conecte a conta acessando `/api/google/connect`. O callback devolve o usuário à página inicial.

#### Endpoints de leitura

- `GET /api/google/status` — estado da integração nesta sessão.
- `GET /api/google/connect` — inicia o consentimento OAuth.
- `POST /api/google/disconnect` — revoga o token de acesso quando possível e remove os tokens armazenados.
- `GET /api/google/gmail/messages?q=...&max_results=10` — lista mensagens por pesquisa Gmail.
- `GET /api/google/gmail/messages/{message_id}` — metadados e snippet da mensagem.
- `GET /api/google/drive/files?q=relatorio&page_size=10` — pesquisa arquivos pelo nome.
- `GET /api/google/calendar/events?max_results=10` — próximos eventos do calendário principal.
- `GET /api/google/docs/{document_id}` — conteúdo estrutural do documento Google Docs.
- `GET /api/google/sheets/{spreadsheet_id}/values/{range}` — valores de um intervalo, por exemplo `Sheet1!A1:C10`.

Os endpoints são somente leitura. Esta primeira etapa não envia e-mails, edita arquivos, cria eventos nem altera planilhas.

#### Segurança e limites

- Tokens de acesso e refresh são criptografados com Fernet antes de serem persistidos no PostgreSQL; a chave de criptografia permanece apenas nas variáveis privadas do Render.
- Cada sessão do navegador recebe seu próprio registro de token. Não exponha os endpoints através de um proxy que compartilhe a sessão de um usuário com outro.
- Não registre tokens nem inclua chaves OAuth no frontend, no GitHub ou nos logs.
- Solicita escopos de leitura de Gmail, Drive, Calendar, Docs e Sheets. O Google pode exigir verificação da aplicação e, dependendo do tipo de conta/escopo, revisão adicional antes de permitir usuários externos. Em modo de teste, tokens de atualização podem expirar; verifique as regras atuais da tela de consentimento.
- Se a chave Fernet for perdida, os tokens armazenados não poderão ser recuperados; se for trocada, os usuários precisarão conectar novamente.
- A integração não cria o banco automaticamente: `DATABASE_URL` deve apontar para um PostgreSQL provisionado. Se as variáveis estiverem ausentes, as rotas retornam estado não configurado e as funções existentes continuam funcionando.

### Configurar a API gratuita do Google Gemini

O Matheus AI usa uma API compatível com OpenAI, então é possível conectar o Gemini alterando somente as variáveis de ambiente, sem trocar a interface nem a base RAG. A disponibilidade gratuita e os limites dependem do modelo, da conta e das regras atuais do Google.

1. Crie uma chave em [Google AI Studio](https://aistudio.google.com/app/apikey).
2. No painel do Render, abra o serviço do Matheus AI e acesse **Environment**.
3. Defina estas variáveis:

```dotenv
MODEL_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL_NAME=gemini-3.8-flash
OPENAI_API_KEY=COLOQUE_A_CHAVE_DO_GEMINI_AQUI
```

4. Salve as alterações e aguarde o novo deploy.
5. Teste uma conversa simples no site e confira os logs do Render se houver erro.

**Segurança e custos:** mantenha a chave somente nas variáveis privadas do Render; nunca a coloque no código, no navegador ou em commits. Consulte [preços e limites oficiais do Gemini API](https://ai.google.dev/gemini-api/docs/pricing) antes de uso contínuo. O nível gratuito tem limites sujeitos a mudança e, segundo a política do Google para esse nível, os dados enviados podem ser usados para melhorar os produtos. Não envie segredos ou dados pessoais sensíveis. Essa alteração configura o provedor de texto; a edição de imagens continua usando a integração separada com Hugging Face.

Se o modelo acima não estiver disponível na sua conta, confira os IDs atuais na [documentação oficial de modelos](https://ai.google.dev/gemini-api/docs/models) e atualize `MODEL_NAME`.

## Segurança e limitações

- Não executa comandos de shell enviados pelo chat.
- Não acessa arquivos pessoais nem automatiza o sistema operacional.
- A ferramenta de cálculo aceita somente expressões aritméticas limitadas.
- Não envie senhas, tokens ou dados sensíveis ao chat.
- A análise de imagens depende de suporte multimodal no provedor/modelo.
- Este é um ponto de partida, não uma aplicação auditada para uso público. Antes de abrir o acesso publicamente, configure autenticação, limites de uso, monitoramento e política de privacidade.

## Estrutura

```
app/main.py             # API, personalidade e recuperação de conhecimento
static/index.html       # interface web
data/knowledge/         # documentos de conhecimento personalizados
data/training/          # orientação para futuros dados de fine-tuning
requirements.txt
.env.example
Dockerfile
render.yaml
```

## Edição de imagens com IA

Para ativar o botão **Editar foto com IA**, configure `HF_TOKEN` no ambiente do Render com um token da Hugging Face que tenha acesso a Inference Providers. A integração usa `Qwen/Qwen-Image-Edit` via provedor `fal-ai`; disponibilidade e cobrança dependem da conta e do provedor. Opcionalmente, configure `IMAGE_EDIT_MODEL` para outro modelo de edição compatível com image-to-image.


## Integração com GitHub

O painel **Ferramentas → GitHub** usa um GitHub App instalado nos repositórios que o usuário autorizar. A chave privada e os tokens temporários ficam somente no backend. O painel permite listar os repositórios da instalação, escolher um repositório, ler um arquivo, enviar seu conteúdo ao chat e preparar uma alteração em uma nova branch com confirmação explícita. A branch padrão não é modificada.

### Configuração obrigatória no GitHub

1. Crie um GitHub App em **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Defina a **Setup URL** como `https://SEU-SERVICO.onrender.com/api/github/callback`.
3. Ative a permissão de repositório **Contents: Read and write**. A permissão Metadata de leitura é concedida automaticamente. Não habilite permissões adicionais sem necessidade.
4. Gere uma chave privada do App e guarde o arquivo PEM com segurança.
5. Copie o **App ID** e o **App slug** para as variáveis de ambiente.
6. Instale o App escolhendo **Only select repositories** e marque apenas os repositórios desejados.
7. Configure no Render `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_SESSION_SECRET` e `PUBLIC_APP_URL`. O valor de `GITHUB_APP_PRIVATE_KEY` é o PEM inteiro; em variáveis de ambiente que não preservem quebras de linha, use `\\n`. Gere `GITHUB_SESSION_SECRET` com um gerador criptograficamente seguro, com pelo menos 32 bytes.
8. Faça deploy e abra **Ferramentas → GitHub → Conectar GitHub**.

O endpoint de instalação cria tokens temporários limitados ao repositório selecionado e à permissão Contents necessária. As alterações são gravadas numa branch separada. Revise o diff e abra um pull request manualmente no GitHub antes de mesclar. A sessão de conexão é mantida em cookie assinado, HttpOnly e SameSite=Lax; use HTTPS em produção. Não compartilhe a chave privada do App nem a inclua no repositório.

## Criação de imagens com IA

A ADA-M inclui um Estúdio de Imagens integrado ao menu **+ → Ferramentas → Criar imagem com IA**. A geração usa o modelo `@cf/black-forest-labs/flux-1-schnell` via Cloudflare Workers AI. A imagem aparece na conversa e pode ser salva pelo usuário.

### Configuração no Render

Configure estas variáveis privadas no serviço:

- `CLOUDFLARE_ACCOUNT_ID`: ID da conta Cloudflare.
- `CLOUDFLARE_API_TOKEN`: token de API com permissão Workers AI (Read e Write, conforme a configuração da conta).
- `IMAGE_GENERATION_MODEL`: opcional; padrão `@cf/black-forest-labs/flux-1-schnell`.

Crie o token no painel da Cloudflare, mantenha-o somente nas variáveis do Render e nunca o coloque no frontend ou no GitHub. O endpoint usa limite básico de três gerações por minuto por IP/processo e aceita descrições de até 1.800 caracteres.

A Cloudflare informa uma franquia de 10.000 Neurons por dia no Workers AI Free; o consumo varia conforme o modelo e a execução. Ao exceder a franquia diária, novas gerações podem falhar até a renovação do limite. Consulte a página oficial de [preços do Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) e o painel de uso antes de ampliar o uso.

A integração não altera o modelo principal de conversa, a leitura em voz alta, a biblioteca de arquivos nem as demais ferramentas. A criação de imagens fica indisponível até que as duas variáveis obrigatórias sejam configuradas.


## Personalidade e estado afetivo simulado

A camada `app/companion.py` adiciona identidade conversacional consistente e sinais afetivos contextuais (alegria, serenidade, curiosidade, empatia, confiança, frustração e surpresa). O estado é isolado por sessão e pode ser persistido no PostgreSQL já configurado em `DATABASE_URL`. A camada não altera os pesos do modelo e não afirma consciência ou sentimentos subjetivos. Sem PostgreSQL, o fallback é temporário em memória. O endpoint `GET /api/companion/state` informa os valores da sessão sem expor mensagens. Consulte [docs/personalidade-e-emocoes.md](docs/personalidade-e-emocoes.md) para detalhes e limitações.
