# Matheus AI

Assistente pessoal independente para programação, Linux, Termux, automação, pesquisa, aprendizado e escrita.

## Recursos
- Interface de chat responsiva em português.
- Upload de imagens JPG, PNG e WebP para análise visual (o modelo/provedor precisa oferecer visão).
- Anexos de PDF com extração de texto e arquivos de texto/código comuns, até 5 MB por arquivo.
- Backend FastAPI com endpoint `/api/chat`.
- Compatibilidade com APIs de chat no formato OpenAI.
- Configuração por variáveis de ambiente.
- Ferramentas locais limitadas a cálculos aritméticos e horário UTC.
- Preparado para deploy web no Render.

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
- `APP_API_KEY`: opcional; se definida, exige o cabeçalho `X-App-Key` nas chamadas à API.

## Deploy no Render
O blueprint `render.yaml` cria somente o serviço web. **Ele não hospeda automaticamente os pesos do modelo.** Configure um endpoint de modelo acessível pela internet em `MODEL_BASE_URL`, o nome em `MODEL_NAME` e os segredos nas variáveis de ambiente do Render. Não coloque chaves no código nem no repositório.

## Laboratório de cibersegurança

O Dockerfile instala Nuclei (release oficial fixada em v3.11.1) e o backend oferece execução real com opções limitadas. Todos os scans exigem hosts exatos em SECURITY_ALLOWED_HOSTS; use somente alvos seus ou com autorização formal.

### Configurar no Render
1. Em Environment, configure SECURITY_ALLOWED_HOSTS com hosts permitidos separados por vírgulas, por exemplo sos01.com.br,www.sos01.com.br.
2. Para ZAP, configure ZAP_API_URL com a URL HTTPS da instância ZAP isolada e ZAP_API_KEY com a chave da API. O Matheus AI não hospeda ZAP; não exponha a API publicamente.
3. Opcional: SECURITY_SCAN_TIMEOUT define o limite em segundos (15–180; padrão 90). NUCLEI_BIN só deve mudar se o binário estiver em outro caminho.
4. Faça deploy e teste primeiro em staging.

### Integrações
- POST /api/security/audit-headers: auditoria passiva de cabeçalhos.
- POST /api/security/nuclei: executa Nuclei com categorias fixas misconfig, exposure e ssl, taxa de 5 requisições/s, concorrência 5, sem Interactsh e com timeout. Não aceita flags ou templates enviados pelo usuário.
- POST /api/security/zap-scan: inicia spider do ZAP e lê alertas passivos; não inicia active scan. Requer ZAP_API_URL e ZAP_API_KEY.
- OWASP PTK: ferramenta independente no navegador, não um scanner backend.

A chave global opcional APP_API_KEY é aplicada às APIs via X-App-Key. Se ativada, o frontend atual precisará ser atualizado para enviar esse cabeçalho. Não exponha a API publicamente sem autenticação e limites de uso. Achados precisam de revisão manual.

## Segurança e limitações
- Não executa comandos de shell enviados pelo chat.
- Não acessa arquivos pessoais nem automatiza o sistema operacional.
- A ferramenta de cálculo aceita somente expressões aritméticas limitadas.
- Não envie senhas, tokens ou dados sensíveis ao chat.
- A análise de imagens depende de suporte multimodal no provedor/modelo. A edição que devolve uma nova imagem ainda exige integração separada com um serviço de geração/edição de imagens.
- Este é um ponto de partida funcional, não uma aplicação auditada para uso público. Antes de abrir o acesso publicamente, configure autenticação, limites de uso, monitoramento e política de privacidade.

## Estrutura
```
app/main.py       # API FastAPI
static/index.html # interface web
requirements.txt
.env.example
Dockerfile
render.yaml
```


## Edição de imagens com IA

Para ativar o botão **Editar foto com IA**, configure `HF_TOKEN` no ambiente do Render com um token da Hugging Face que tenha acesso a Inference Providers. A integração usa `Qwen/Qwen-Image-Edit` via provedor `fal-ai`; disponibilidade e cobrança dependem da conta e do provedor. Opcionalmente, configure `IMAGE_EDIT_MODEL` para outro modelo de edição compatível com image-to-image.
