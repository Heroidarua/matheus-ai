# ADA-M Live na VPS (Vosk PT-BR)

O modo Live usa um WebSocket servido pelo próprio backend ADA-M. O navegador envia áudio PCM mono a 16 kHz; o Vosk reconhece português brasileiro na VPS; a transcrição entra no fluxo normal de `/api/chat`; e a resposta é falada pela Tiny-Voca já configurada.

## Instalação na VPS

Depois de integrar esta alteração à branch principal, execute nesta ordem:

```bash
cd /opt/ada-m
git pull origin main
bash scripts/install-vosk-model.sh
systemctl restart ada-m.service
systemctl is-active ada-m.service
curl -fsS http://127.0.0.1:8001/health
```

O instalador adiciona `vosk==0.3.45`, baixa o modelo pequeno PT-BR (aprox. 31 MB), extrai em `/opt/ada-m/models/vosk-model-small-pt-0.3` e valida o carregamento. O modelo é carregado sob demanda na primeira conexão Live.

**Não reinicie o serviço antes de executar o instalador**, pois o backend importa o módulo Vosk ao iniciar.

## Verificação

1. Abra a ADA-M pelo mesmo domínio HTTPS usado normalmente.
2. Toque em **Live** e permita o microfone.
3. Aguarde o status indicar que a VPS está conectada.
4. Fale uma frase curta e aguarde a resposta do Gemma 4 e o áudio Tiny-Voca.
5. Durante a fala da ADA-M, fale novamente para testar a interrupção.

O endpoint WebSocket é `/api/live/ws`. O áudio precisa chegar em PCM mono, 16 bits, 16 kHz. O reconhecimento e o modelo Vosk permanecem na VPS; Gemma 4 e Tiny-Voca continuam usando os serviços que já estão configurados.

## Rollback

Se o teste falhar, não remova o modelo nem apague os arquivos antigos do agente. Reponha a versão anterior do código na VPS e reinicie `ada-m.service`. Os arquivos antigos do LiveKit são mantidos temporariamente para facilitar esse retorno; eles não são usados pelo novo botão Live.
