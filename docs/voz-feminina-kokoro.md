# Voz feminina natural da ADA-M (Kokoro)

A integração do chat usa um proxy no backend Matheus AI. A chave do serviço TTS fica somente nas variáveis do Render; ela nunca é enviada ao navegador.

## 1. Serviço de voz no Render

Crie um **novo Web Service** conectado ao repositório:

- Repositório: `Heroidarua/matheus-kokoro-tts`
- Branch: `deploy/kokoro-pf-dora-cpu`
- Runtime: Docker
- Plano: comece pelo Free para validar; se houver encerramento por memória, use um plano com mais RAM
- Health check: `/health`

O serviço usa Kokoro-82M com ONNX Runtime em CPU e a voz feminina brasileira `pf_dora`. Não usa CUDA. O primeiro build baixa os arquivos do modelo e pode demorar.

Configure no serviço de voz:
- `TTS_API_KEY`: crie um segredo aleatório forte e guarde-o.

Depois do deploy, confira:
- `https://SEU-SERVICO-TTS.onrender.com/health` deve retornar `status: ok`, `voice: pf_dora` e `language: pt-BR`.
- A URL raiz deve identificar `Kokoro-82M` e `pf_dora`.

## 2. Conectar ao Matheus AI

No serviço principal `matheus-ai` do Render, adicione:

- `TTS_API_URL`: URL base do serviço TTS, por exemplo `https://SEU-SERVICO-TTS.onrender.com` (sem `/v1/audio/speech` no final).
- `TTS_API_KEY`: exatamente o mesmo segredo configurado no serviço de voz.
- `TTS_VOICE`: `pf_dora`.

Não altere `MODEL_BASE_URL`, `MODEL_NAME` ou `OPENAI_API_KEY` para configurar a voz. Salve as variáveis e faça deploy do PR de integração no Matheus AI.

## 3. Como funciona

- O navegador envia o texto ao endpoint `/api/tts/speech` do Matheus AI.
- O backend encaminha a solicitação ao serviço Kokoro e mantém a chave privada.
- Se o serviço TTS não estiver configurado ou falhar, o chat volta automaticamente à voz nativa do navegador.
- A rota `/api/tts/status` e o painel de diagnóstico informam se a integração está configurada.
- O áudio é gerado sob demanda; não é armazenado como histórico.

## 4. PostgreSQL para estado emocional

A integração emocional funciona sem PostgreSQL, mas nesse caso o estado é temporário e pode se perder em reinicializações do Render. Para persistir:
- Crie/seleciona um banco PostgreSQL no Render.
- Copie a Internal Database URL para `DATABASE_URL` no serviço `matheus-ai`, preferencialmente usando a URL interna quando os serviços estiverem na mesma região.
- Após o deploy, consulte `/api/companion/state` com a autenticação exigida pela aplicação. O campo `storage` agora verifica a conectividade real e não apenas a presença da variável.

Não cole chaves, URLs com senha ou tokens no chat.