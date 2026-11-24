# ADA-M — arquitetura de conversação Live

## Objetivo

Adicionar uma conversa por voz em tempo real sem substituir o chat digitado, o modelo Gemma 4, as ferramentas, a memória ou a voz feminina Tiny-Voca PT-BR já integrada na VPS.

## Componentes

- **Backend ADA-M:** FastAPI, endpoint `/api/chat`, endpoint `/api/livekit/token` e proxy TTS `/api/tts/speech`.
- **LiveKit Cloud:** transporte WebRTC e sala isolada por sessão.
- **Agente LiveKit:** VAD Silero, STT Deepgram Nova-3 em pt-BR e encaminhamento do histórico ao backend oficial ADA-M.
- **Navegador:** cliente LiveKit, captura de microfone, apresentação de status e reprodução dos WAV recebidos do proxy TTS.
- **Tiny-Voca:** serviço privado na VPS em `127.0.0.1:8002`, voz feminina `F`, áudio mono 24 kHz.

## Fluxo

```text
Pessoa fala
  → microfone WebRTC
  → LiveKit Cloud
  → VAD + STT pt-BR
  → agente encaminha o histórico a POST /api/chat
  → Gemma 4 gera a resposta
  → agente publica texto de resposta
  → navegador chama POST /api/tts/speech
  → backend chama Tiny-Voca privado
  → navegador reproduz WAV
```

## Segurança

- O token LiveKit é curto, emitido pelo backend e limitado à sala da sessão.
- A chave e o segredo LiveKit permanecem exclusivamente no servidor.
- A chave TTS permanece no backend; o navegador acessa apenas o proxy ADA-M.
- O modo Live só inicia após ação explícita no botão.
- O usuário pode encerrar a sessão a qualquer momento.

## Voz e experiência

A saída de voz usa o Tiny-Voca PT-BR já configurado, sem trocar para Kokoro ou SpeechSynthesis do navegador. O cliente divide a resposta em frases e solicita cada WAV com velocidade 1.19. Como o motor atual gera um arquivo completo por chamada, a reprodução é progressiva por frases, não token a token.

Durante a reprodução, a detecção de fala do participante local cancela o áudio e a requisição pendente (barge-in). A captura WebRTC permanece ativa para que o agente possa transcrever a nova fala. O cancelamento de eco e a supressão de ruído são solicitados ao navegador, mas o comportamento real precisa ser validado em aparelhos físicos e com fones/alto-falante.

## Configuração necessária

No backend ADA-M:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_AGENT_NAME=ada-m-voice`
- `TTS_API_URL=http://127.0.0.1:8002`
- `TTS_API_KEY`
- `TTS_VOICE=F`

No agente LiveKit Cloud:
- `ADA_M_API_URL`
- `ADA_M_APP_API_KEY`, somente se `APP_API_KEY` estiver habilitada
- `LIVEKIT_AGENT_NAME=ada-m-voice`
- `LIVEKIT_STT_MODEL=deepgram/nova-3`
- `LIVEKIT_STT_LANGUAGE=pt-BR`

O LiveKit Cloud injeta as credenciais próprias do worker. Não duplicar chaves privadas no frontend ou no GitHub.

## Critérios de validação

- Chat digitado e modo de voz tradicional permanecem funcionando.
- O botão Live conecta, ativa o microfone e encerra a sessão sem recarregar a página.
- A fala é reconhecida em pt-BR e respondida pelo backend oficial ADA-M.
- A resposta usa a voz feminina Tiny-Voca atual.
- Interromper a ADA-M cancela a reprodução e permite falar novamente.
- Falhas de STT, TTS, token e reconexão exibem mensagens compreensíveis.

## Limitações conhecidas

O pipeline STT → LLM → TTS não é o mesmo sistema speech-to-speech nativo do GPT Live. O Tiny-Voca atual não oferece streaming de áudio: cada frase precisa ser sintetizada como WAV antes de tocar. A latência, a qualidade de interrupção e o comportamento do cancelamento de eco precisam ser medidos em testes reais. O uso do STT LiveKit Inference pode consumir créditos ou gerar cobrança conforme o plano e a franquia da conta.
