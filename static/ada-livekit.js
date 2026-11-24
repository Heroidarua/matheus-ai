import { Room, RoomEvent } from "https://cdn.jsdelivr.net/npm/livekit-client@2.9.6/dist/livekit-client.esm.mjs";

const startButton = document.getElementById("livekit-voice-button");
const statusLabel = document.getElementById("livekit-voice-status");

if (startButton && statusLabel) {
  let room = null;
  let connecting = false;
  let playbackGeneration = 0;
  let playbackAbort = null;
  let activeAudio = null;
  let activeAudioUrl = null;

  function setStatus(message, visible = true) {
    statusLabel.textContent = message;
    statusLabel.hidden = !visible;
  }

  function stopPlayback() {
    playbackGeneration += 1;
    if (playbackAbort) { playbackAbort.abort(); playbackAbort = null; }
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.removeAttribute("src");
      activeAudio.load();
      activeAudio = null;
    }
    if (activeAudioUrl) { URL.revokeObjectURL(activeAudioUrl); activeAudioUrl = null; }
  }

  function splitIntoSpeechParts(value) {
    const clean = String(value || "").replace(/https?:\/\/\S+/g, "link").replace(/\s+/g, " ").trim();
    if (!clean) return [];
    const sentences = clean.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) || [clean];
    const parts = [];
    for (const sentence of sentences) {
      const part = sentence.trim();
      if (!part) continue;
      if (part.length <= 420) parts.push(part);
      else parts.push(...(part.match(/.{1,380}(?:[,;:]\s+|$)/g) || [part]).map(x => x.trim()).filter(Boolean));
    }
    return parts;
  }

  async function speakWithTinyVoca(text) {
    stopPlayback();
    const generation = playbackGeneration;
    const parts = splitIntoSpeechParts(text);
    for (const part of parts) {
      if (generation !== playbackGeneration || !room) return;
      const controller = new AbortController();
      playbackAbort = controller;
      setStatus("ADA-M preparando a voz…");
      try {
        const response = await fetch("/api/tts/speech", {
          method: "POST", credentials: "same-origin", signal: controller.signal,
          headers: { "Content-Type": "application/json", "Accept": "audio/wav" },
          body: JSON.stringify({ text: part, speed: 1.19 })
        });
        if (!response.ok) {
          let detail = "O serviço Tiny-Voca não conseguiu gerar o áudio.";
          try { const payload = await response.json(); if (payload.detail) detail = payload.detail; } catch {}
          throw new Error(detail);
        }
        const blob = await response.blob();
        if (!blob.size || generation !== playbackGeneration || !room) return;
        activeAudioUrl = URL.createObjectURL(blob);
        const audio = new Audio(activeAudioUrl);
        activeAudio = audio;
        audio.preload = "auto";
        setStatus("ADA-M falando…");
        await new Promise((resolve, reject) => {
          let settled = false;
          const finish = error => {
            if (settled) return;
            settled = true;
            audio.onended = null;
            audio.onerror = null;
            error ? reject(error) : resolve();
          };
          audio.onended = () => finish();
          audio.onerror = () => finish(new Error("Falha ao reproduzir o áudio."));
          audio.play().catch(finish);
        });
        if (activeAudio === audio) activeAudio = null;
        if (activeAudioUrl) { URL.revokeObjectURL(activeAudioUrl); activeAudioUrl = null; }
      } catch (error) {
        if (error?.name === "AbortError" || generation !== playbackGeneration) return;
        console.error("ADA-M Live: erro no TTS Tiny-Voca", error);
        setStatus(error instanceof Error ? error.message : "Falha na reprodução da voz.");
        return;
      } finally {
        if (playbackAbort === controller) playbackAbort = null;
      }
    }
    if (generation === playbackGeneration && room) setStatus("Sua vez. Pode falar…");
  }

  function resetControls(message = "Modo Live encerrado.", visible = false) {
    startButton.disabled = false;
    startButton.classList.remove("livekit-active");
    startButton.textContent = "🎙️ Live";
    startButton.setAttribute("aria-label", "Iniciar conversa ao vivo");
    setStatus(message, visible);
  }

  async function disconnect(message = "Modo Live encerrado.") {
    const activeRoom = room;
    room = null;
    stopPlayback();
    if (activeRoom) {
      try { await activeRoom.localParticipant.setMicrophoneEnabled(false); } catch {}
      try { await activeRoom.disconnect(); } catch {}
    }
    resetControls(message);
  }

  async function connect() {
    if (connecting) return;
    if (room) { await disconnect(); return; }
    connecting = true;
    startButton.disabled = true;
    setStatus("Preparando conversa ao vivo…");
    try {
      await window.__adaStopBrowserVoice?.();
      const tokenResponse = await fetch("/api/livekit/token", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: "{}"
      });
      if (!tokenResponse.ok) {
        let detail = "Não foi possível iniciar o modo Live.";
        try { const payload = await tokenResponse.json(); if (payload.detail) detail = payload.detail; } catch {}
        throw new Error(detail);
      }
      const credentials = await tokenResponse.json();
      if (!credentials.server_url || !credentials.participant_token) throw new Error("O servidor não retornou as credenciais de voz.");

      const activeRoom = new Room({
        adaptiveStream: true, dynacast: true, stopLocalTrackOnUnpublish: true,
        audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      room = activeRoom;

      activeRoom.on(RoomEvent.DataReceived, payload => {
        try {
          const message = JSON.parse(new TextDecoder().decode(payload));
          if (message?.type !== "ada_m_debug") return;
          const labels = {
            agent_ready: "Conectada. Pode conversar comigo.",
            speech_detected: "Estou ouvindo você…",
            stt_partial: "Entendendo sua fala…",
            stt_received: message.message || "Entendi. Vou responder…",
            stt_timeout: "Não consegui entender. Pode repetir?",
            llm_started: "Estou pensando…",
            agent_thinking: "Estou preparando uma resposta…",
            agent_speaking: "Vou responder agora…",
            agent_listening: "Pode falar…",
            assistant_text_ready: "Resposta pronta. Preparando minha voz…",
            session_error: message.message || "A sessão de voz encontrou um erro.",
            backend_response: message.message || "Resposta recebida do servidor.",
            first_token: "Já estou formulando a resposta…",
            llm_finished: "Texto concluído. Gerando áudio…",
            backend_error: message.message || "Não consegui acessar a ADA-M."
          };
          if (labels[message.stage]) setStatus(labels[message.stage]);
        } catch (error) { console.warn("ADA-M Live: diagnóstico inválido", error); }
      });

      activeRoom.registerTextStreamHandler("lk.transcription", async (reader, participantInfo) => {
        try {
          const text = await reader.readAll();
          const attributes = reader.info?.attributes || {};
          const isUserTranscription = Boolean(attributes["lk.transcribed_track_id"]);
          if (isUserTranscription || participantInfo?.identity === activeRoom.localParticipant.identity || !text.trim()) return;
          console.info("ADA-M Live: resposta recebida; usando Tiny-Voca.");
          await speakWithTinyVoca(text);
        } catch (error) {
          if (error?.name !== "AbortError") {
            console.warn("ADA-M Live: falha ao receber resposta", error);
            setStatus("Não consegui receber a resposta da ADA-M.");
          }
        }
      });

      activeRoom.on(RoomEvent.ParticipantConnected, participant => {
        if (participant.identity !== activeRoom.localParticipant.identity) setStatus("Agente conectado. Pode falar…");
      });
      activeRoom.on(RoomEvent.ParticipantDisconnected, participant => {
        if (participant.identity !== activeRoom.localParticipant.identity) {
          stopPlayback();
          setStatus("O agente foi desconectado. Aguardando…");
        }
      });
      activeRoom.on(RoomEvent.ActiveSpeakersChanged, speakers => {
        const userIsSpeaking = speakers.some(speaker => speaker.identity === activeRoom.localParticipant.identity);
        if (userIsSpeaking && (activeAudio || playbackAbort)) {
          stopPlayback();
          setStatus("Interrompida. Estou ouvindo você…");
        } else if (userIsSpeaking) setStatus("Estou ouvindo você…");
      });
      activeRoom.on(RoomEvent.Disconnected, () => {
        if (room === activeRoom) {
          room = null;
          stopPlayback();
          resetControls("Conexão encerrada.");
        }
      });

      setStatus("Conectando ao serviço de voz…");
      await activeRoom.connect(credentials.server_url, credentials.participant_token);
      setStatus("Ativando microfone…");
      await activeRoom.localParticipant.setMicrophoneEnabled(true);
      startButton.disabled = false;
      startButton.classList.add("livekit-active");
      startButton.textContent = "Encerrar Live";
      startButton.setAttribute("aria-label", "Encerrar conversa ao vivo");
      setStatus("Conectada. Pode falar comigo…");
    } catch (error) {
      console.error("ADA-M Live: falha na conexão", error);
      if (room) { const failedRoom = room; room = null; try { await failedRoom.disconnect(); } catch {} }
      stopPlayback();
      resetControls(error instanceof Error ? error.message : "Falha ao conectar ao modo Live.", true);
    } finally {
      connecting = false;
      startButton.disabled = false;
    }
  }

  startButton.addEventListener("click", connect);
  window.addEventListener("beforeunload", () => { stopPlayback(); try { room?.disconnect(); } catch {} });
}
