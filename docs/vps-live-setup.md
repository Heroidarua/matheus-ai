# ADA-M Live na VPS (Whisper.cpp PT-BR)

O modo Live envia áudio PCM mono a 16 kHz pelo WebSocket da ADA-M. O backend detecta o fim da fala por silêncio, transcreve a frase completa com Whisper.cpp Base multilíngue quantizado Q5_1 e envia o texto ao fluxo normal de conversa. Gemma 4 e Tiny-Voca continuam sendo os provedores de resposta e voz.

## Instalação na VPS

Depois de integrar esta alteração à branch principal, execute:

```bash
cd /opt/ada-m
git pull origin main
sudo bash scripts/install-whisper-cpp.sh
systemctl restart ada-m.service
systemctl is-active ada-m.service
curl -fsS http://127.0.0.1:8001/health
```

O instalador compila Whisper.cpp para CPU com um job de compilação para limitar o pico de memória, instala o executável em `/usr/local/bin/whisper-cli` e baixa o modelo multilíngue Base Q5_1 para `/opt/ada-m/models/ggml-base-q5_1.bin`. A primeira compilação pode levar alguns minutos.

## Como funciona

- O navegador continua enviando áudio PCM mono, 16 bits, 16 kHz.
- O backend mantém um pequeno pré-buffer para preservar o início das palavras.
- A frase é fechada após aproximadamente 1,4 segundo de silêncio. O detector usa limiar RMS adaptativo ao ruído ambiente, histerese durante a fala e pré-buffer de aproximadamente 450 ms para preservar o início das palavras. O limite de segurança por trecho é de 60 segundos.
- Só depois do fim da fala o Whisper transcreve o áudio. Não há envio de parciais para interromper a voz da ADA-M.
- O navegador suspende o envio do microfone enquanto a Tiny-Voca está gerando ou reproduzindo a resposta, para impedir que o próprio alto-falante seja reconhecido como uma nova fala.
- A transcrição completa segue para o Gemma 4; a resposta continua sendo falada pela Tiny-Voca.

O detector usa um limiar RMS adaptativo com histerese: aprende lentamente o ruído de fundo enquanto não há fala e usa um limiar menor para acompanhar sílabas mais baixas durante a frase. O pré-buffer maior ajuda a não cortar o começo da primeira palavra.

## Verificação

1. Abra a ADA-M pelo domínio HTTPS habitual.
2. Toque em **Live** e permita o microfone.
3. Diga uma frase completa, sem pausas longas no meio.
4. Aguarde o status de conversão e a resposta falada.
5. Repita com frases curtas e longas, com e sem fone.

A versão inicial não interrompe automaticamente a fala da ADA-M quando você começa a falar. Isso é intencional: evita que o áudio reproduzido pelo próprio aparelho seja confundido com a sua voz. O botão Live continua disponível para encerrar a sessão.

## Ajustes opcionais

As variáveis abaixo podem ser adicionadas ao ambiente do serviço, se necessário:

- `ADA_LIVE_ASR=whisper_cpp` — mecanismo padrão. Use `vosk` apenas como fallback temporário.
- `WHISPER_CLI_PATH=/usr/local/bin/whisper-cli`
- `WHISPER_MODEL_PATH=/opt/ada-m/models/ggml-base-q5_1.bin`
- `ADA_LIVE_VAD_RMS=0.0035` — limiar inicial do detector de voz; o valor é ajustado lentamente conforme o ruído ambiente.
- `ADA_LIVE_VAD_SILENCE=1.4` — silêncio necessário para fechar uma frase, em segundos.
- `ADA_LIVE_MAX_UTTERANCE=60` — limite de segurança para a duração de um trecho, em segundos.
- `ADA_LIVE_MIN_SPEECH=0.35` — duração mínima de voz para aceitar um trecho.
- `ADA_LIVE_WHISPER_THREADS=2` — threads usadas na transcrição.

Não altere o endpoint do modelo principal, as variáveis TTS ou os arquivos/variáveis antigos do LiveKit.

## Fallback e rollback

Para voltar temporariamente ao Vosk sem remover o Whisper, defina `ADA_LIVE_ASR=vosk` no ambiente do serviço e mantenha instalado o modelo Vosk em `/opt/ada-m/models/vosk-model-small-pt-0.3`. Reinicie `ada-m.service`.

Para reverter completamente a alteração, volte o código da aplicação ao commit anterior e reinicie o serviço. O instalador não apaga os arquivos Vosk nem os componentes antigos do LiveKit.
