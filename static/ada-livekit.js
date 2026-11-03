import { Room, RoomEvent, Track } from "https://cdn.jsdelivr.net/npm/livekit-client@2.9.6/dist/livekit-client.esm.mjs";

const startButton = document.getElementById("livekit-voice-button");
const statusLabel = document.getElementById("livekit-voice-status");

if (startButton && statusLabel) {
  let room = null;
  let audioElements = new Set();
  let connecting = false;

  function setStatus(message) {
    statusLabel.textContent = message;
  }

  function removeAudioElements() {
    for (const element of audioElements) {
      try {
        element.pause();
        element.srcObject = null;
        element.remove();
      } catch {}
    }
    audioElements.clear();
  }

  function resetControls(message = "Conversa em tempo real encerrada.") {
    startButton.disabled = false;
    startButton.classList.remove("livekit-active");
    startButton.textContent = "🎙️ Conversar em tempo real";
    setStatus(message);
  }

  async function disconnect(message) {
    const activeRoom = room;
    room = null;
    removeAudioElements();
    if (activeRoom) {
      try {
        await activeRoom.localParticipant.setMicrophoneEnabled(false);
      } catch {}
      try {
        await activeRoom.disconnect();
      } catch {}
    }
    resetControls(message);
  }

  async function connect() {
    if (connecting) return;
    if (room) {
      await disconnect();
      return;
    }

    connecting = true;
    startButton.disabled = true;
    setStatus("Preparando conexão segura…");

    try {
      window.__adaStopBrowserVoice?.();

      const tokenResponse = await fetch("/api/livekit/token", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });

      if (!tokenResponse.ok) {
        let detail = "Não foi possível iniciar o modo LiveKit.";
        try {
          const body = await tokenResponse.json();
          if (body.detail) detail = body.detail;
        } catch {}
        throw new Error(detail);
      }

      const credentials = await tokenResponse.json();
      if (!credentials.server_url || !credentials.participant_token) {
        throw new Error("O servidor não retornou as credenciais de voz.");
      }

      const activeRoom = new Room({
        adaptiveStream: true,
        dynacast: true,
        stopLocalTrackOnUnpublish: true,
      });
      room = activeRoom;

      activeRoom.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
        try {
          const message = JSON.parse(new TextDecoder().decode(payload));
          if (message?.type !== "ada_m_debug") return;
          console.info("ADA-M LiveKit diagnóstico:", message.stage, message.message);
          const labels = {
            agent_ready: "Agente pronto. Pode falar.",
            speech_detected: "Detectei sua voz; aguardando a transcrição…",
            stt_partial: "Reconhecendo sua fala…",
            stt_received: "Entendi sua fala. Enviando ao Gemma 4…",
            stt_timeout: "Detectei sua voz, mas a transcrição falhou. Verifique a etapa de reconhecimento.",
            llm_started: "Sua fala chegou ao Gemma 4; gerando resposta…",
            backend_response: message.message,
            first_token: "Gemma 4 respondeu. Preparando a voz…",
            llm_finished: "Texto gerado. Aguardando o áudio…",
            backend_error: message.message
          };
          setStatus(labels[message.stage] || message.message || "Diagnóstico recebido.");
          statusLabel.dataset.diagnosticStage = message.stage || "";
        } catch (error) {
          console.warn("ADA-M LiveKit: diagnóstico inválido", error);
        }
      });

      activeRoom.on(RoomEvent.ParticipantConnected, (participant) => {
        console.info("ADA-M LiveKit: remote participant connected", participant.identity);
        setStatus("Agente conectado. Microfone ativo; pode falar.");
      });

      activeRoom.on(RoomEvent.ParticipantDisconnected, (participant) => {
        console.info("ADA-M LiveKit: remote participant disconnected", participant.identity);
        setStatus("Agente desconectado. Aguardando reconexão…");
      });

      activeRoom.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (speakers.some((speaker) => speaker.identity !== activeRoom.localParticipant.identity)) {
          setStatus("A ADA-M está respondendo em áudio…");
        } else if (activeRoom.state === "connected") {
          setStatus("Conectado. Pode falar; a ADA-M está ouvindo.");
        }
      });

      activeRoom.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        console.info("ADA-M LiveKit: remote track subscribed", track.kind, participant.identity);
        if (track.kind !== Track.Kind.Audio) return;
        const element = track.attach();
        element.autoplay = true;
        element.setAttribute("playsinline", "");
        element.style.display = "none";
        document.body.appendChild(element);
        audioElements.add(element);
        element.play().catch(() => {
          setStatus("Conectado. Se não ouvir a ADA-M, verifique o volume do navegador.");
        });
      });

      activeRoom.on(RoomEvent.TrackUnsubscribed, (track) => {
        for (const element of track.detach()) {
          audioElements.delete(element);
          element.remove();
        }
      });

      activeRoom.on(RoomEvent.Disconnected, () => {
        if (room === activeRoom) {
          room = null;
          removeAudioElements();
          resetControls("Conexão encerrada.");
        }
      });

      setStatus("Conectando à sala de voz…");
      await activeRoom.connect(credentials.server_url, credentials.participant_token);
      setStatus("Conectado à sala. Ativando microfone…");
      await activeRoom.localParticipant.setMicrophoneEnabled(true);
      console.info("ADA-M LiveKit: microphone enabled", activeRoom.localParticipant.isMicrophoneEnabled);

      const remoteAgent = Array.from(activeRoom.remoteParticipants.values()).find(
        (participant) => participant.identity !== activeRoom.localParticipant.identity
      );

      startButton.disabled = false;
      startButton.classList.add("livekit-active");
      startButton.textContent = "Encerrar conversa";
      setStatus(remoteAgent
        ? "Agente conectado. Microfone ativo; pode falar."
        : "Microfone ativo. Aguardando o agente entrar na sala…");
    } catch (error) {
      console.error("ADA-M LiveKit connection failed:", error);
      if (room) {
        const failedRoom = room;
        room = null;
        try { await failedRoom.disconnect(); } catch {}
      }
      removeAudioElements();
      resetControls(error instanceof Error ? error.message : "Falha ao conectar ao LiveKit.");
    } finally {
      connecting = false;
      startButton.disabled = false;
    }
  }

  startButton.addEventListener("click", connect);
  window.addEventListener("beforeunload", () => {
    try { room?.disconnect(); } catch {}
  });
}
