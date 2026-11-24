# ADA-M — agente de voz no LiveKit Cloud

Este agente é um serviço independente do backend principal. Ele recebe áudio pelo WebRTC, transcreve em português brasileiro e encaminha o histórico textual ao endpoint oficial `/api/chat`. A resposta é enviada como texto ao navegador, que gera o áudio pelo serviço Tiny-Voca PT-BR já integrado à ADA-M.

## Arquitetura

```text
Navegador ADA-M
  └─ WebRTC → LiveKit Cloud
       └─ Agente ADA-M
            ├─ STT: LiveKit Inference / Deepgram Nova-3 (pt-BR)
            ├─ LLM: POST /api/chat → Gemma 4 + contexto ADA-M
            └─ Texto de resposta → navegador
                 └─ POST /api/tts/speech
                      └─ Tiny-Voca PT-BR privado (voz F, 1.19x)
```

O agente não chama o Gemma diretamente. Toda geração passa pelo backend ADA-M para preservar instruções, memória, ferramentas e contexto do projeto. O áudio é gerado pelo Tiny-Voca já instalado na VPS; nenhuma voz Kokoro ou voz do navegador é selecionada pelo modo Live.

## Configuração do agente

No LiveKit Cloud, configure os seguintes Secrets:

| Variável | Valor |
|---|---|
| `ADA_M_API_URL` | URL HTTPS do backend ADA-M, por exemplo `https://matheus-ai.onrender.com` |
| `ADA_M_APP_API_KEY` | Mesmo valor de `APP_API_KEY` do backend, somente se essa proteção estiver habilitada |
| `LIVEKIT_AGENT_NAME` | `ada-m-voice` |
| `LIVEKIT_STT_MODEL` | `deepgram/nova-3` |
| `LIVEKIT_STT_LANGUAGE` | `pt-BR` |

O LiveKit Cloud injeta `LIVEKIT_URL`, `LIVEKIT_API_KEY` e `LIVEKIT_API_SECRET` no worker. Não coloque essas credenciais no frontend ou no GitHub. O serviço TTS não precisa ser configurado no worker: a chave do Tiny-Voca permanece no backend ADA-M.

No serviço Web da ADA-M, mantenha `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` e `LIVEKIT_AGENT_NAME=ada-m-voice`. O backend usa essas credenciais para emitir o token curto do navegador em `POST /api/livekit/token`.

## Deploy

1. Abra o projeto no [LiveKit Cloud](https://cloud.livekit.io/).
2. Instale a [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/).
3. Na pasta `voice-agent`, autentique com `lk cloud auth`.
4. Confira o projeto com `lk project list` e selecione o correto com `lk project set-default "NOME_DO_PROJETO"`.
5. Se ainda não houver configuração de agente, execute `lk agent create`.
6. Cadastre os Secrets descritos acima no painel do LiveKit Cloud.
7. Publique com `lk agent deploy`.
8. Confira com `lk agent status` e `lk agent logs`.
9. Aguarde o deploy do backend ADA-M e teste o botão **🎙️ Live** no navegador.

## Voz e interrupção

- O navegador recebe a transcrição final do agente e solicita o áudio em `/api/tts/speech`.
- O backend usa `TTS_API_URL`, `TTS_API_KEY` e `TTS_VOICE=F` para chamar o Tiny-Voca privado.
- A velocidade padrão do modo Live é `1.19`.
- O áudio é gerado em WAV completo por frase; o Tiny-Voca atual não oferece streaming nativo.
- Ao detectar a fala do usuário durante a reprodução, o cliente cancela o áudio e a solicitação pendente, permitindo que a sessão LiveKit reconheça a nova fala.
- A conversa usa o histórico da própria sessão LiveKit. A sessão de voz não herda automaticamente todo o histórico de uma conversa digitada já aberta no navegador.

## Limites e segurança

- O fluxo é STT → Gemma 4 via backend ADA-M → Tiny-Voca. Não é um modelo speech-to-speech nativo.
- Confira os limites mensais de minutos, sessões simultâneas e créditos de Inference no plano LiveKit Cloud utilizado.
- Um agente em escala zero pode levar alguns segundos para iniciar.
- O backend e o TTS precisam estar acessíveis pela internet interna/privada configurada; o TTS da VPS deve continuar escutando apenas em `127.0.0.1:8002`.
- Nunca grave áudio ou transcrições sensíveis nos logs.
- Nunca commite arquivos `.env`, secrets ou credenciais LiveKit.
