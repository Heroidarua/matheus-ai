# Worker matheus-stt (STT Whisper pt-BR)

Proxy de transcrição de voz para o Matheus AI. Roda na Cloudflare Workers,
usa o Workers AI (`@cf/openai/whisper`, large-v3-turbo) para transcrever
áudio pt-BR. Plano free: 10.000 neurons/dia (~10 min de áudio/dia).

## Arquivos

- `src/index.js` — código do Worker (cole no dashboard ou use via wrangler).
- `wrangler.jsonc` — config para deploy via CLI (`npx wrangler deploy`).

## Deploy via dashboard (mais simples)

1. dash.cloudflare.com → **Workers & Pages → Create → Worker**.
2. Nome: `matheus-stt`.
3. Cole o conteúdo de `src/index.js` no editor.
4. **Settings → Bindings & Secrets → Add → Capability → AI**.
5. **Deploy**.
6. URL final: `https://matheus-stt.<seu-subdominio>.workers.dev`.

## Uso

O backend do Matheus AI (Render) chama:

```
POST https://matheus-stt.<subdominio>.workers.dev/stt
Content-Type: audio/webm
Body: bytes do áudio (WebM/Opus do MediaRecorder)

→ 200 { "text": "transcrição em pt-BR" }
```
