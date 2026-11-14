# Executar o Matheus AI localmente

Este guia permite executar a API e a interface no seu computador, sem Render e sem créditos de inferência na nuvem. O modelo roda no próprio dispositivo; o desempenho depende da RAM, CPU e GPU.

## Opção recomendada para Linux desktop: Ollama + FastAPI

### 1. Verifique o computador

Execute no terminal:

```bash
uname -m
free -h
nproc
lscpu | grep -E 'Model name|Architecture|CPU\(s\)'
df -h "$HOME"
```

Tenha espaço livre para o modelo e para as dependências. O modelo Qwen2.5 3B ocupa cerca de 1,9 GB para download; o uso real de RAM é maior e varia com o contexto. Em máquinas com pouca memória, experimente primeiro `qwen2.5:1.5b`.

### 2. Instale e teste o Ollama

Siga a instalação oficial para seu sistema: https://ollama.com/download

No Linux desktop, depois de instalar:

```bash
ollama --version
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

Faça uma pergunta no chat do Ollama e saia com `/bye`. Em instalações Linux sem serviço automático, abra outro terminal e execute `ollama serve`. Não inicie uma segunda instância se o serviço já estiver ativo.

Modelos para testar:
- `qwen2.5:1.5b`: menor, para computadores com recursos limitados.
- `qwen2.5:3b`: ponto de partida equilibrado para português e tarefas gerais.
- `qwen2.5:7b`: pode responder melhor, mas exige mais memória; considere apenas se o computador tiver RAM suficiente.

Os tamanhos dos arquivos não representam a RAM total necessária. Comece com um contexto moderado e teste a velocidade antes de aumentar.

### 3. Prepare o projeto

Clone o repositório e entre na pasta:

```bash
git clone https://github.com/Heroidarua/matheus-ai.git
cd matheus-ai
```

Crie um ambiente Python e instale as dependências:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure as variáveis sem publicar chaves:

```bash
cp .env.example .env
```

Edite o arquivo `.env` e confira estes valores:

```dotenv
MODEL_BASE_URL=http://127.0.0.1:11434/v1
MODEL_NAME=qwen2.5:3b
OPENAI_API_KEY=ollama
KNOWLEDGE_DIR=data/knowledge
APP_API_KEY=
```

O `APP_API_KEY` pode ficar vazio para uso estritamente local. Não exponha a API à rede pública sem configurar autenticação.

### 4. Inicie o Matheus AI

Com o Ollama funcionando, na pasta do projeto e com o ambiente virtual ativado:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000 no navegador. O servidor fica disponível apenas no próprio computador porque usa `127.0.0.1`.

### 5. Verifique a API e a base de conhecimento

Em outro terminal:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/knowledge/status
curl -fsS http://127.0.0.1:11434/api/tags
```

O primeiro deve indicar que a aplicação está ativa; o segundo informa métricas da base; o terceiro lista os modelos disponíveis no Ollama. Depois, envie uma pergunta de teste pelo navegador.

## Se estiver usando Android, Termux ou Ubuntu em PRoot

O instalador padrão do Ollama pode não funcionar em ambientes sem systemd, com limitações de arquitetura ou bibliotecas. Não repita comandos que falharam sem verificar o erro. Nesses ambientes, uma alternativa é `llama.cpp` com um modelo GGUF quantizado, mas a instalação e o desempenho dependem da arquitetura do dispositivo. Consulte o guia oficial: https://github.com/ggml-org/llama.cpp

Se o modelo rodar em outro dispositivo da sua rede local, configure `MODEL_BASE_URL` para o endpoint desse dispositivo. Use apenas uma rede confiável e não exponha a porta do modelo à internet.

## Limitações importantes

- Isso executa o modelo localmente, mas não significa que o modelo foi treinado com os seus documentos. A pasta `data/knowledge` continua funcionando por recuperação RAG.
- O recurso de edição de imagens atualmente depende de um provedor externo e de `HF_TOKEN`; ele não se torna offline automaticamente.
- Navegação na web, dados atuais e integrações externas não funcionam offline sem ferramentas adicionais.
- O primeiro download do modelo exige internet. Depois de baixado, o chat básico pode funcionar offline.
- Não envie senhas, tokens ou documentos sensíveis para o chat, e mantenha o repositório privado se seus arquivos forem pessoais.
