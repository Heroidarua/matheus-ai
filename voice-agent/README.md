# ADA-M — agente de voz no LiveKit Cloud

Este agente é um serviço independente do backend principal. Ele entra em salas LiveKit, recebe áudio pelo WebRTC, transcreve em português brasileiro, encaminha o histórico textual para o endpoint oficial `/api/chat` e reproduz a resposta usando o Kokoro PF Dora.

## Arquitetura

```text
Navegador / app ADA-M
    └── WebRTC → LiveKit Cloud
                    └── Agente hospedado no LiveKit Cloud
                          ├── STT: LiveKit Inference / Deepgram Nova-3
                          ├── LLM: POST /api/chat → Gemma 4 + memória + RAG + ferramentas
                          └── TTS: Kokoro PF Dora (OpenAI-compatible)
```

O agente não chama o Gemma diretamente. Toda geração passa pelo backend ADA-M para preservar instruções, ferramentas, busca e contexto do projeto. O histórico textual da sala é enviado em cada turno (até 20 mensagens).

## Hospedagem sem mensalidade

A recomendação é hospedar este agente diretamente no **LiveKit Cloud — plano Build (gratuito)**, em vez de criar um Background Worker pago no Render.

O plano gratuito tem limites mensais compartilhados por conta/projetos: 1.000 minutos de sessão de agente, até 5 sessões simultâneas, US$ 2,50 de crédito de LiveKit Inference e limites adicionais de tráfego/observabilidade. Ao atingir os limites gratuitos, novas solicitações podem ser bloqueadas até a renovação mensal. O plano Build também pode colocar o agente em escala zero quando não há sessões, causando cold start de até 10–20 segundos.

A ADA-M continua usando o backend no Render e o Kokoro já existente. O plano gratuito do LiveKit não torna automaticamente os serviços externos gratuitos: mantenha o Render e o provedor de TTS em planos sem custo e confira os limites de cada um. Se o crédito de Inference acabar, o STT pode parar até o próximo ciclo ou até usar outro provedor com franquia gratuita.

## Deploy no LiveKit Cloud

Pré-requisitos: projeto LiveKit Cloud no plano Build, LiveKit CLI atual instalado e acesso ao repositório.

1. Entre em [LiveKit Cloud](https://cloud.livekit.io/) e crie/abra um projeto no plano Build.
2. Instale a [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/) no computador.
3. No terminal, entre na pasta `voice-agent` deste repositório e autentique:

   ```bash
   lk cloud auth
   ```

4. Selecione o projeto correto, caso tenha mais de um:

   ```bash
   lk project list
   lk project set-default "NOME_DO_PROJETO"
   ```

5. Crie o agente e faça o primeiro deploy:

   ```bash
   lk agent create
   ```

   O comando cria `livekit.toml` com o ID do agente e faz o build/deploy na infraestrutura do LiveKit Cloud. Guarde esse arquivo localmente; ele identifica o agente nos próximos deploys. Não precisa ser enviado ao GitHub.

6. Cadastre os segredos/variáveis do agente pelo painel do LiveKit Cloud (Agent → Secrets) ou pela opção `--secrets-file` da CLI. Configure:

   | Variável | Valor |
   |---|---|
   | `ADA_M_API_URL` | `https://matheus-ai.onrender.com` |
   | `ADA_M_APP_API_KEY` | Mesmo valor de `APP_API_KEY` no backend, somente se essa chave estiver habilitada |
   | `ADA_M_TTS_BASE_URL` | URL do Kokoro PF Dora terminando em `/v1` |
   | `ADA_M_TTS_API_KEY` | Chave do Kokoro, somente se o serviço exigir |
   | `ADA_M_TTS_VOICE` | `pf_dora` |
   | `ADA_M_TTS_SPEED` | `1.19` |
   | `LIVEKIT_STT_MODEL` | `deepgram/nova-3` |
   | `LIVEKIT_STT_LANGUAGE` | `pt-BR` |
   | `LIVEKIT_AGENT_NAME` | `ada-m-voice` |

   **Não cadastre manualmente** `LIVEKIT_URL`, `LIVEKIT_API_KEY` ou `LIVEKIT_API_SECRET` no agente hospedado: o LiveKit Cloud injeta essas credenciais automaticamente. Não coloque chaves no GitHub, no frontend ou em mensagens de chat.

7. No serviço Web `matheus-ai` do Render, mantenha as variáveis de servidor `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` e `LIVEKIT_AGENT_NAME=ada-m-voice`. O backend precisa dessas credenciais para emitir o token do navegador em `POST /api/livekit/token`. Salve e aguarde o redeploy do Web Service.

8. Confira o agente e os logs:

   ```bash
   lk agent status
   lk agent logs
   ```

9. Abra a ADA-M e teste o botão LiveKit com uma conversa curta. Confirme STT em pt-BR, resposta via endpoint ADA-M/Gemma 4, áudio Kokoro e interrupção da fala.

## Atualizar o agente

Depois de alterar os arquivos desta pasta:

```bash
lk agent deploy
```

## Variáveis e comportamento

- O LiveKit Cloud fornece automaticamente `LIVEKIT_URL`, `LIVEKIT_API_KEY` e `LIVEKIT_API_SECRET` ao container hospedado.
- `LIVEKIT_AGENT_NAME` deve permanecer `ada-m-voice`, igual ao nome de dispatch usado pelo backend.
- `ADA_M_TTS_BASE_URL` deve apontar para a API OpenAI-compatible do Kokoro, com sufixo `/v1`.
- `ADA_M_TTS_SPEED` aceita valores entre 0.7 e 1.3; padrão recomendado: `1.19`.
- `LIVEKIT_STT_MODEL` usa `deepgram/nova-3` por padrão e `LIVEKIT_STT_LANGUAGE` usa `pt-BR`.

## Limitações conhecidas

- O fluxo é STT → Gemma 4 via ADA-M → TTS. O LiveKit gerencia streaming e interrupções, mas não é um modelo speech-to-speech nativo full-duplex.
- O agente cria uma sessão própria no backend ADA-M por meio de seu cliente HTTP. Portanto, a memória de longo prazo da sessão de voz é independente da sessão já aberta no navegador; unir as duas exige uma ponte autenticada de identidade/sessão.
- No plano Build, o agente pode dormir quando não houver sessões e levar até 10–20 segundos para iniciar ao receber uma nova chamada.
- O limite gratuito de minutos é compartilhado entre os projetos LiveKit da mesma conta. A franquia de Inference é limitada; monitore o uso no painel.
- O backend e o Kokoro no Render podem entrar em sleep no plano gratuito, adicionando latência ao primeiro pedido. Isso é independente do LiveKit.

## Segurança

- Nunca commite `.env`, `secrets.env`, `livekit.toml` com dados sensíveis ou credenciais.
- As chaves LiveKit do backend ficam somente nas variáveis de ambiente do Render.
- As variáveis privadas do agente ficam nos Secrets do LiveKit Cloud.
- O agente não grava áudio ou transcrições em disco. Os logs operacionais não devem conter o conteúdo das mensagens.
