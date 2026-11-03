from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterable
from typing import Any

import httpx
from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, ChatContext, JobContext, cli, llm, inference
from livekit.plugins import openai, silero

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ada-m-livekit-agent")

ADA_M_API_URL = os.getenv("ADA_M_API_URL", "").strip().rstrip("/")
ADA_M_APP_API_KEY = os.getenv("ADA_M_APP_API_KEY", "").strip()
ADA_M_TTS_BASE_URL = os.getenv("ADA_M_TTS_BASE_URL", "").strip().rstrip("/")
ADA_M_TTS_API_KEY = os.getenv("ADA_M_TTS_API_KEY", "").strip()
ADA_M_TTS_VOICE = os.getenv("ADA_M_TTS_VOICE", "pf_dora").strip() or "pf_dora"
ADA_M_TTS_SPEED = float(os.getenv("ADA_M_TTS_SPEED", "1.19"))
LIVEKIT_STT_MODEL = os.getenv("LIVEKIT_STT_MODEL", "deepgram/nova-3").strip()
LIVEKIT_STT_LANGUAGE = os.getenv("LIVEKIT_STT_LANGUAGE", "pt-BR").strip()

if not ADA_M_API_URL:
    raise RuntimeError("Configure ADA_M_API_URL com a URL HTTPS do backend ADA-M.")
if not ADA_M_TTS_BASE_URL:
    raise RuntimeError(
        "Configure ADA_M_TTS_BASE_URL com a URL OpenAI-compatible do Kokoro, terminando em /v1."
    )
if not 0.7 <= ADA_M_TTS_SPEED <= 1.3:
    raise RuntimeError("ADA_M_TTS_SPEED deve ficar entre 0.7 e 1.3.")


def _chat_history(chat_ctx: ChatContext) -> list[dict[str, str]]:
    """Converte apenas mensagens textuais da sessão LiveKit para o contrato ADA-M."""
    messages: list[dict[str, str]] = []
    for item in chat_ctx.items:
        if getattr(item, "type", None) != "message":
            continue
        role = getattr(item, "role", None)
        if role not in {"user", "assistant"}:
            continue
        content = getattr(item, "text_content", "") or ""
        content = str(content).strip()
        if content:
            messages.append({"role": role, "content": content[:12000]})
    return messages[-20:]


class AdaMVoiceAgent(Agent):
    """Agente de voz: LiveKit faz mídia/STT/TTS; ADA-M continua gerando as respostas."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__(
            instructions=(
                "Você é a interface de voz da ADA-M. Responda em português brasileiro. "
                "A geração da resposta é encaminhada ao backend oficial da ADA-M; "
                "não invente respostas locais."
            )
        )
        self._client = client

    async def llm_node(
        self,
        chat_ctx: ChatContext,
        tools: list[Any],
        model_settings: Any,
    ) -> AsyncIterable[str | llm.ChatChunk]:
        messages = _chat_history(chat_ctx)
        logger.info("LLM node invoked; messages=%s last_role=%s", len(messages), messages[-1]["role"] if messages else "none")
        if not messages or messages[-1]["role"] != "user":
            yield "Não consegui identificar sua última fala. Pode repetir?"
            return

        headers = {"Accept": "text/event-stream"}
        if ADA_M_APP_API_KEY:
            headers["X-App-Key"] = ADA_M_APP_API_KEY

        payload = {
            "messages": messages,
            "mode": "normal",
            "response_length": "curta",
            "web_search": False,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST",
                f"{ADA_M_API_URL}/api/chat",
                headers=headers,
                json=payload,
            ) as response:
                logger.info("ADA-M /api/chat responded with HTTP %s", response.status_code)
                response.raise_for_status()
                first_token_logged = False
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("ADA-M returned a malformed SSE event")
                        continue
                    token = event.get("token")
                    if isinstance(token, str) and token:
                        if not first_token_logged:
                            logger.info("ADA-M first response token received")
                            first_token_logged = True
                        yield token
                    elif event.get("detail"):
                        logger.error("ADA-M stream emitted an error event")
                        yield "A ADA-M não conseguiu concluir a resposta. Tente novamente."
                        return
                logger.info("ADA-M response stream finished; first_token=%s", first_token_logged)
        except httpx.TimeoutException:
            logger.warning("Timeout calling ADA-M chat API")
            yield "A ADA-M demorou para responder. Tente falar novamente."
        except httpx.HTTPStatusError as exc:
            logger.error("ADA-M chat API returned HTTP %s", exc.response.status_code)
            yield "Não consegui acessar o serviço de conversa da ADA-M agora."
        except httpx.HTTPError as exc:
            logger.error("ADA-M chat API connection failed: %s", type(exc).__name__)
            yield "A conexão com a ADA-M foi interrompida. Tente novamente."


server = AgentServer()


@server.rtc_session(agent_name=os.getenv("LIVEKIT_AGENT_NAME", "ada-m-voice"))
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

    # Silero VAD detects speech start/end locally; Deepgram transcribes the audio.
    vad = silero.VAD.load()
    voice_session = AgentSession(
        vad=vad,
        transcription_timeout=8.0,
        stt=inference.STT(
            model=LIVEKIT_STT_MODEL,
            language=LIVEKIT_STT_LANGUAGE,
        ),
        tts=openai.TTS(
            model="kokoro",
            voice=ADA_M_TTS_VOICE,
            base_url=ADA_M_TTS_BASE_URL,
            api_key=ADA_M_TTS_API_KEY or "not-required",
            speed=ADA_M_TTS_SPEED,
            response_format="wav",
        ),
    )

    @voice_session.on("user_input_transcribed")
    def on_user_input_transcribed(event: Any) -> None:
        # Never write the user's spoken content to logs.
        logger.info(
            "STT transcript received; final=%s chars=%s language=%s",
            getattr(event, "is_final", False),
            len(getattr(event, "transcript", "") or ""),
            getattr(event, "language", None) or "unknown",
        )

    @voice_session.on("user_state_changed")
    def on_user_state_changed(event: Any) -> None:
        logger.info("User voice state: %s -> %s", getattr(event, "old_state", "unknown"), getattr(event, "new_state", "unknown"))

    @voice_session.on("agent_state_changed")
    def on_agent_state_changed(event: Any) -> None:
        logger.info("Agent state: %s -> %s", getattr(event, "old_state", "unknown"), getattr(event, "new_state", "unknown"))

    @voice_session.on("user_transcription_timeout")
    def on_user_transcription_timeout(event: Any) -> None:
        logger.warning("Speech detected but STT transcript timed out; duration=%s", getattr(event, "duration", "unknown"))

    logger.info(
        "Starting ADA-M voice session in room %s; STT=%s language=%s TTS=%s",
        ctx.room.name, LIVEKIT_STT_MODEL, LIVEKIT_STT_LANGUAGE, ADA_M_TTS_VOICE,
    )
    try:
        await voice_session.start(
            room=ctx.room,
            agent=AdaMVoiceAgent(client),
        )
        await ctx.wait_for_shutdown()
    finally:
        await voice_session.aclose()
        await client.aclose()
        logger.info("ADA-M voice session ended in room %s", ctx.room.name)


if __name__ == "__main__":
    cli.run_app(server)
