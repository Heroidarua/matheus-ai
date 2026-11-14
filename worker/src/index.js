// matheus-stt — proxy de STT (Whisper pt-BR) para o Matheus AI
// Recebe POST /stt com áudio (WebM/Opus do navegador) e devolve { text }
//
// Deploy: Cloudflare Workers & Pages → Create Worker → cola este arquivo
//         → adicione o binding AI (Capability → AI) → Deploy.
// URL final: https://matheus-stt.<subdominio>.workers.dev

const ACCOUNT_ID = "523b77a14a08cedb4c6136a7f27ed57e";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response("ok", { headers: cors() });
    }

    if (url.pathname === "/" || url.pathname === "/health") {
      return Response.json({ ok: true, service: "matheus-stt" }, { headers: cors() });
    }

    if (url.pathname !== "/stt" || request.method !== "POST") {
      return Response.json({ error: "Use POST /stt com o áudio no body." }, { status: 405, headers: cors() });
    }

    const audio = await request.arrayBuffer();
    if (audio.byteLength < 100) {
      return Response.json({ error: "Áudio vazio ou muito pequeno." }, { status: 400, headers: cors() });
    }
    if (audio.byteLength > 8 * 1024 * 1024) {
      return Response.json({ error: "Áudio excede 8 MB." }, { status: 413, headers: cors() });
    }

    try {
      let text;

      if (env.AI) {
        const out = await env.AI.run("@cf/openai/whisper", {
          audio: new Uint8Array(audio),
          language: "pt",
        });
        text = (out?.text || "").trim();
      } else {
        if (!env.AI_TOKEN) {
          return Response.json(
            { error: "Worker sem binding AI nem secret AI_TOKEN." },
            { status: 500, headers: cors() }
          );
        }
        const form = new FormData();
        form.append("file", new Blob([audio]), "turno.webm");
        form.append("model", "@cf/openai/whisper");
        form.append("language", "pt");
        const ai = await fetch(
          `https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/ai/v1/audio/transcriptions`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${env.AI_TOKEN}` },
            body: form,
          }
        );
        if (!ai.ok) {
          const detail = await ai.text();
          return Response.json(
            { error: "Whisper falhou", status: ai.status, detail },
            { status: 502, headers: cors() }
          );
        }
        const data = await ai.json();
        text = (data?.result?.text || "").trim();
      }

      return Response.json({ text: text.slice(0, 2000) }, { headers: { ...cors(), "content-type": "application/json" } });
    } catch (err) {
      return Response.json(
        { error: "Erro interno no STT", detail: String(err) },
        { status: 500, headers: cors() }
      );
    }
  },
};

function cors() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "POST, GET, OPTIONS",
    "access-control-allow-headers": "content-type",
  };
}
