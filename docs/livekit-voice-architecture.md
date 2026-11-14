# Plano de integração — voz em tempo real com LiveKit

## Decisão técnica

Adicionar o LiveKit Agents como um serviço de voz independente para a ADA-M. O chat HTTP atual continua sendo a experiência padrão e permanece disponível como fallback.

**Não substituir:** Gemma 4 31B, endpoint `/api/chat`, memória, pesquisa, ferramentas, interface principal nem o serviço TTS já configurado.

## O que existe hoje

A revisão da branch `main` identificou:

- Backend FastAPI em `app/main.py`.
- Modelo principal fixado em `gemma4:31b`, com `MODEL_BASE_URL` e `OPENAI_API_KEY` definidos no ambiente.
- Resposta do chat por streaming em `POST /api/chat`.
- Proxy TTS em `POST /api/tts/speech`, usando `TTS_API_URL`, `TTS_API_KEY` e `TTS_VOICE`.
- Frontend estático em `static/index.html`, que hoje usa Web Speech API para reconhecimento e fala nativa do navegador.
- O modo de voz atual envia transcrições para o chat e monitora interrupções no navegador; não é uma sessão de áudio full-duplex via WebRTC.

## Arquitetura recomendada

```text
Navegador ADA-M
  └─ WebRTC / LiveKit room
       └─ LiveKit Agent (serviço separado)
            ├─ VAD + detecção de turnos
            ├─ STT em pt-BR
            ├─ Adaptador para o contexto da ADA-M
            │    └─ POST /api/chat (Gemma 4 31B + memória + ferramentas)
            └─ TTS configurável
                 └─ serviço Kokoro atual, após teste de compatibilidade
```

A sessão de voz deve chamar o backend existente da ADA-M para gerar respostas. Assim, a personalidade, o histórico e os recursos do chat continuam centralizados. Não se deve chamar o endpoint do modelo diretamente pelo agente sem reproduzir o contexto e as políticas do backend.

## Decisões e limites

1. **Gemma permanece como LLM principal.** O agente deve consumir o endpoint autenticado da ADA-M ou um adaptador equivalente; não migrar automaticamente para LiveKit Inference.
2. **STT e TTS são provedores independentes.** Selecionar serviços que suportem português brasileiro, streaming e interrupção. Validar latência, preço, limites e política de dados antes de habilitar produção.
3. **Kokoro é candidato, não pressuposto.** O proxy atual espera uma API no formato `/v1/audio/speech`; testar o formato real do serviço configurado antes de conectar.
4. **LiveKit exige credenciais e infraestrutura.** Criar projeto LiveKit (Cloud ou servidor próprio) e configurar URL, API key e API secret apenas no servidor. Nunca expor o secret no JavaScript.
5. **WebRTC não significa automaticamente full-duplex.** O pipeline STT → LLM → TTS oferece streaming e barge-in; a experiência de ouvir e falar simultaneamente depende do agente, VAD, provedor e implementação do cliente.
6. **Render Free pode não ser adequado para um agente persistente.** Verificar disponibilidade de background worker, processo contínuo, consumo e custo do plano antes de ativar o serviço.

## Variáveis de ambiente previstas

Somente no servidor:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_AGENT_NAME` (nome lógico do agente)
- `ADA_M_INTERNAL_URL` (URL privada/interna do backend ADA-M quando disponível)
- `ADA_M_INTERNAL_API_KEY` (credencial servidor-a-servidor, diferente de qualquer chave pública)

As variáveis de STT/TTS devem ser adicionadas apenas após escolher os provedores e confirmar suas APIs. Não commitar valores reais.

## Plano de entrega incremental

### Fase 1 — preparação
- Criar serviço independente para o agente.
- Fixar versões compatíveis de `livekit-agents` e plugins.
- Implementar health check e logs sem áudio/transcrições sensíveis.
- Não alterar a experiência atual nem iniciar o agente automaticamente.

### Fase 2 — integração de backend (implementada nesta branch)
- Endpoint `POST /api/livekit/token` com token de 10 minutos, sala nova por chamada e permissões limitadas a publicar/assinar áudio.
- O endpoint valida a origem, aplica intervalo mínimo entre emissões por sessão e exige as credenciais apenas no servidor.
- O token despacha explicitamente o agente `ada-m-voice`.
- O worker envia o histórico textual da sessão ao fluxo existente `/api/chat`; a geração continua no Gemma 4 via backend ADA-M.

### Fase 3 — interface (implementada nesta branch)
- Botão separado **Conversar em tempo real** na área de Ferramentas.
- Solicitação do microfone somente após ação explícita do usuário.
- Conexão WebRTC via LiveKit Client SDK; reprodução das faixas de áudio recebidas.
- Encerramento da sala pelo mesmo botão.
- O modo de voz atual do navegador continua disponível como alternativa.

### Fase 4 — testes antes da produção
- Testar Chrome/Edge desktop e Android.
- Testar português brasileiro, ruído, silêncio, falas longas e nomes próprios.
- Testar barge-in enquanto a ADA-M fala.
- Testar reconexão, token expirado e indisponibilidade de STT/TTS.
- Medir latência ponta a ponta e custo por minuto.
- Só então habilitar a opção em produção.

## Critérios para considerar pronto

- O chat digitado e o modo de voz atual continuam funcionando.
- A sessão LiveKit não expõe credenciais privadas.
- As respostas passam pelo contexto e pelas regras da ADA-M.
- Interrupção interrompe tanto o áudio quanto a geração pendente.
- O usuário pode desligar o modo LiveKit sem recarregar a página.
- Há fallback claro quando o serviço de voz não está configurado.

## Estado desta branch

Esta branch adiciona o endpoint de tokens, o botão de conexão no navegador e o cliente LiveKit. O serviço worker permanece separado e deve ser implantado como processo contínuo com o nome `ada-m-voice`. O modo LiveKit só conecta quando `LIVEKIT_URL`, `LIVEKIT_API_KEY` e `LIVEKIT_API_SECRET` estiverem configurados no backend e no worker. O STT usa LiveKit Inference (Deepgram Nova-3) e pode gerar cobrança conforme a conta. Ainda não houve teste de ponta a ponta com credenciais reais; não considerar pronto para produção até validar STT, Kokoro, latência, barge-in e reconexão. Nenhum segredo foi adicionado ao repositório e nenhum serviço pago foi criado automaticamente.
