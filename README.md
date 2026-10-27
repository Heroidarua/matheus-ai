# Matheus AI

Assistente pessoal independente para conversas gerais, escrita, estudos, tecnologia e ajuda prática. O projeto combina um modelo de linguagem configurável com uma base de conhecimento própria.

## Personalização com seus dados

O projeto agora suporta **RAG (busca e recuperação de conhecimento)**: antes de responder, o backend procura trechos relevantes nos arquivos Markdown e TXT de `data/knowledge/` e inclui os trechos selecionados no contexto do modelo.

Isso personaliza as respostas com informações do projeto sem retreinar os pesos do modelo. O sistema de busca é lexical e leve, feito com a biblioteca padrão do Python; não precisa de banco vetorial nem de outra API. A qualidade depende do modelo configurado e de como os documentos são escritos.

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
