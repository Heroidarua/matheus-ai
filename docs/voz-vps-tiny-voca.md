# Voz local pt-BR da ADA-M — tiny-voca

A ADA-M pode gerar áudio diretamente na VPS usando o projeto
[Haple/tiny-voca-ptbr-kokoro](https://github.com/Haple/tiny-voca-ptbr-kokoro).
O serviço é separado do FastAPI principal, escuta somente em `127.0.0.1:8002`
e é chamado pelo proxy já existente em `/api/tts/speech`.

## Por que este motor

- Modelo ONNX de aproximadamente 21,4 MB e 4,5 milhões de parâmetros.
- Voz feminina (`F`) e masculina (`M`) em português brasileiro.
- CPU, um thread, sem GPU e sem PyTorch.
- Áudio WAV mono a 24 kHz.
- Código e pesos sob Apache-2.0.
- Sem streaming; cada solicitação gera o WAV completo.

O modelo foi treinado com eSpeak NG 1.51. Em outra versão do eSpeak NG,
algumas pronúncias podem mudar. O instalador avisa quando detecta outra versão.

## Instalação na VPS

A partir da raiz do repositório ADA-M:

```bash
sudo bash voice-tts/install-vps.sh
```

O instalador:
1. Instala eSpeak NG e as dependências Python.
2. Clona o modelo oficial em `/opt/ada-m-tts/engine`.
3. Cria um usuário Linux isolado `ada-tts` e um ambiente virtual próprio.
4. Cria o serviço `ada-m-tts.service`, limitado a um núcleo e 384 MiB.
5. Gera uma chave Bearer privada em `/etc/ada-m-tts.env`.
6. Testa a geração de um WAV feminino antes de alterar o ambiente da ADA-M.
7. Configura `TTS_API_URL=http://127.0.0.1:8002`, `TTS_VOICE=F` e a chave no
   `/opt/ada-m/.env`, preservando um backup, e reinicia a ADA-M.

A chave nunca é enviada ao navegador. O serviço TTS não abre porta pública.

## Verificação

```bash
systemctl is-active ada-m-tts.service
curl -fsS http://127.0.0.1:8002/health
journalctl -u ada-m-tts.service -n 50 --no-pager
```

A rota de saúde deve indicar `ready: true`. Para testar pelo chat, use o
botão de teste de voz ou peça à ADA-M para ler uma resposta. O frontend atual
já usa o proxy autenticado `/api/tts/speech` e mantém a voz nativa do navegador
como fallback caso o serviço local esteja indisponível.

## Vozes e ajuste

- `TTS_VOICE=F`: voz feminina.
- `TTS_VOICE=M`: voz masculina.
- A velocidade recebida do frontend é aplicada ao motor (0,7 a 1,3).
- O serviço usa um único thread e serializa as sínteses para limitar recursos.

A voz feminina foi ensinada por áudio sintético do Kokoro; é uma voz pequena
e eficiente, não uma reprodução idêntica à voz original do Kokoro. O projeto
não oferece streaming nem clonagem de voz.
