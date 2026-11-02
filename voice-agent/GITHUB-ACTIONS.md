# ADA-M LiveKit Cloud pelo GitHub Actions

Este fluxo dispensa Termux, Ubuntu, Git local e LiveKit CLI. O GitHub Actions executa a criação e os deploys na nuvem.

## Segredos necessários

No repositório, abra Settings → Secrets and variables → Actions e crie estes repository secrets:

- `LIVEKIT_URL`: `wss://ada-m-ns0yz6ze.livekit.cloud`
- `LIVEKIT_API_KEY`: API Key ID do projeto `ada-m` no LiveKit Cloud.
- `LIVEKIT_API_SECRET`: segredo correspondente à mesma API Key. Não é o ID.
- `SECRET_LIST`: variáveis que o agente precisa em runtime, numa única linha separada por vírgulas.

O ID da API Key que apareceu na configuração do projeto foi `APIP4ihqfkD2Ezg`; ele não substitui o API Secret. Copie o segredo diretamente do painel LiveKit e não o envie por mensagem.

### Exemplo de SECRET_LIST

```text
ADA_M_API_URL=https://matheus-ai.onrender.com,ADA_M_TTS_BASE_URL=https://SEU-HOST-KOKORO.onrender.com/v1,ADA_M_TTS_VOICE=pf_dora,ADA_M_TTS_SPEED=1.19,LIVEKIT_STT_MODEL=deepgram/nova-3,LIVEKIT_STT_LANGUAGE=pt-BR,LIVEKIT_AGENT_NAME=ada-m-voice
```

Substitua `SEU-HOST-KOKORO` pelo host Render atualmente ativo para o serviço Kokoro PF Dora. A URL deve terminar em `/v1`. Se `APP_API_KEY` estiver habilitada no backend Render, acrescente `ADA_M_APP_API_KEY=SEU_VALOR`. Se o Kokoro exigir autenticação, acrescente `ADA_M_TTS_API_KEY=SEU_VALOR`. Não inclua essas variáveis opcionais se não forem necessárias.

Não coloque `LIVEKIT_URL`, `LIVEKIT_API_KEY` ou `LIVEKIT_API_SECRET` em `SECRET_LIST`: o LiveKit Cloud injeta essas credenciais no agente.

## Criar e implantar pela primeira vez

1. Mescle o PR que adiciona `.github/workflows/ada-m-livekit.yml`.
2. Cadastre os quatro repository secrets acima.
3. Abra Actions → ADA-M LiveKit Cloud → Run workflow.
4. Escolha `create` e execute. O LiveKit cria e implanta o agente.
5. O workflow abre automaticamente outro PR contendo `voice-agent/livekit.toml`, com o identificador do agente. Mescle esse segundo PR para salvar a configuração.

## Operações futuras

- `deploy`: publica uma nova versão após alterações em `voice-agent/` e após o `livekit.toml` estar na branch principal.
- `status`: consulta o estado atual do agente.

## Conectar o backend no Render

Depois de criar o agente, configure no serviço Web `matheus-ai` do Render:

- `LIVEKIT_URL`: `wss://ada-m-ns0yz6ze.livekit.cloud`
- `LIVEKIT_API_KEY`: o mesmo API Key ID cadastrado no GitHub.
- `LIVEKIT_API_SECRET`: o mesmo API Secret cadastrado no GitHub.
- `LIVEKIT_AGENT_NAME`: `ada-m-voice`.

Salve e aguarde o redeploy do serviço. O backend usa essas credenciais para emitir tokens ao navegador em `POST /api/livekit/token`.

## Limites

A transcrição está configurada para LiveKit Inference com `deepgram/nova-3`, que consome a franquia de Inference do plano. O agente roda no LiveKit Cloud; não é necessário criar Background Worker no Render. O backend ADA-M e o Kokoro continuam sujeitos aos limites dos seus próprios serviços.

## Segurança

Nunca grave tokens ou API Secrets em arquivos versionados, commits ou mensagens. Mantenha os quatro valores em GitHub Actions Secrets. Se uma chave for exposta, revogue-a no provedor e gere outra.
