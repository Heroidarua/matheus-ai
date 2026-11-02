# ADA-M — agente de voz independente

Este serviço é um worker separado do backend principal. Ele entra em salas LiveKit, recebe áudio pelo WebRTC, transcreve em português brasileiro, encaminha o histórico textual para o endpoint oficial `/api/chat` e reproduz a resposta usando o serviço Kokoro configurado para a ADA-M.

## Fluxo

```text
Navegador / app ADA-M
    └── WebRTC → LiveKit Room
                    └── LiveKit Agent Worker (este serviço)
                          ├── STT: LiveKit Inference / Deepgram Nova-3
                          ├── LLM: POST /api/chat → Gemma 4 + memória + RAG + ferramentas
                          └── TTS: serviço Kokoro compatível com OpenAI
```

O worker não chama o endpoint do Gemma diretamente. Toda geração de resposta passa pelo backend da ADA-M, para manter as instruções, as ferramentas, a busca e o contexto do projeto. O histórico textual da sala é enviado em cada turno (até 20 mensagens).

## Variáveis de ambiente

Configure somente no ambiente do worker; nunca coloque segredos no repositório ou no navegador.

| Variável | Obrigatória | Descrição |
|---|---:|---|
| `LIVEKIT_URL` | Sim | URL WebSocket do projeto LiveKit |
| `LIVEKIT_API_KEY` | Sim | Chave de servidor LiveKit |
| `LIVEKIT_API_SECRET` | Sim | Segredo de servidor LiveKit |
| `LIVEKIT_AGENT_NAME` | Sim | Nome de dispatch; deve ser `ada-m-voice` para coincidir com o backend |
| `ADA_M_API_URL` | Sim | URL HTTPS do backend ADA-M, sem barra final |
| `ADA_M_APP_API_KEY` | Se configurada no backend | Mesmo valor de `APP_API_KEY` da ADA-M |
| `ADA_M_TTS_BASE_URL` | Sim | URL do Kokoro terminando em `/v1` |
| `ADA_M_TTS_API_KEY` | Não | Chave do serviço Kokoro, se exigida |
| `ADA_M_TTS_VOICE` | Não | Voz Kokoro; padrão `pf_dora` |
| `ADA_M_TTS_SPEED` | Não | Velocidade de fala entre 0.7 e 1.3; padrão `1.19` |
| `LIVEKIT_STT_MODEL` | Não | Modelo STT; padrão `deepgram/nova-3` |
| `LIVEKIT_STT_LANGUAGE` | Não | Idioma STT; padrão `pt-BR` |

O STT usa LiveKit Inference e requer credenciais LiveKit válidas e acesso ao modelo escolhido. Confira preços, limites e disponibilidade na conta LiveKit antes de ativar o serviço.

## Executar localmente

A partir desta pasta:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # crie o arquivo com as variáveis da tabela
python agent.py dev
```

Em produção, o Dockerfile inicia o worker com `python agent.py start`.

## Deploy separado

Crie um serviço do tipo **Background Worker** no provedor escolhido, usando esta pasta como diretório raiz e o Dockerfile incluído. No Render, Background Workers exigem plano pago; este repositório não adiciona nem ativa um serviço pago automaticamente.

## Limites desta etapa

- O worker do agente está separado do processo web e não altera o chat digitado nem o modo de voz atual.
- O backend ADA-M emite tokens de sala de curta duração em `/api/livekit/token`, e a interface oferece o botão para entrar/sair do LiveKit. Configure as mesmas credenciais LiveKit no backend e no worker.
- O worker cria uma sessão própria no backend ADA-M por meio de seu cliente HTTP. Assim, a memória de longo prazo da sessão de voz é independente da sessão já aberta no navegador; vincular ambas exige uma ponte autenticada de identidade/sessão, sem expor cookies ou segredos.
- O pipeline é STT → Gemma 4 via ADA-M → TTS. O LiveKit gerencia streaming de áudio e interrupções, mas isso não é o mesmo que um modelo speech-to-speech full-duplex nativo.
- O worker e o backend ainda precisam ser implantados/testados com credenciais reais. Primeiro valide STT, Kokoro, latência, custos e interrupções em uma sala de teste.

## Segurança

- Credenciais LiveKit e chaves de serviço ficam exclusivamente no servidor.
- O cliente HTTP mantém seu cookie de sessão apenas dentro do processo do worker.
- Não são gravados arquivos de áudio nem transcrições em disco por este serviço.
- O worker não registra o conteúdo das mensagens; os logs registram eventos operacionais e códigos HTTP.
