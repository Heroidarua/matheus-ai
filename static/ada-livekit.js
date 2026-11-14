import { Room, RoomEvent } from "https://cdn.jsdelivr.net/npm/livekit-client@2.9.6/dist/livekit-client.esm.mjs";

const startButton = document.getElementById("livekit-voice-button");
const statusLabel = document.getElementById("livekit-voice-status");

if (startButton && statusLabel) {
  let room = null;
  let connecting = false;
  let browserSpeechQueue = Promise.resolve();
  let browserSpeechGeneration = 0;

  function setStatus(message) {
    statusLabel.textContent = message;
  }

  function stopBrowserSpeech() {
    browserSpeechGeneration += 1;
    browserSpeechQueue = Promise.resolve();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }

  function speakWithBrowserVoice(text) {
    const clean = String(text || "").replace(/https?:\\/\\/\\S+/g, "link").trim();
    if (!clean || !("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      setStatus("Resposta recebida, mas a voz do navegador não está disponível.");
      return;
    }
    const generation = browserSpeechGeneration;
    const sentences = clean.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) || [clean];
    browserSpeechQueue = browserSpeechQueue.then(async () => {
      for (const sentence of sentences) {
        if (generation !== browserSpeechGeneration) return;
        const part = sentence.trim();
        if (!part) continue;
        await new Promise((resolve) => {
          const utterance = new SpeechSynthesisUtterance(part);
          utterance.lang = "pt-BR";
          utterance.rate = 1.19;
          utterance.pitch = 1.02;
          utterance.volume = 1;
          const voices = window.speechSynthesis.getVoices();
          const voice = voices.find((item) => /^pt-BR$/i.test(item.lang)) || voices.find((item) => /^pt/i.test(item.lang));
          if (voice) utterance.voice = voice;
          utterance.onstart = () => setStatus("ADA-M falando com a voz do navegador…");
          utterance.onend = resolve;
          utterance.onerror = resolve;
          window.speechSynthesis.speak(utterance);
        });
      }
      if (generation === browserSpeechGeneration && room) setStatus("Sua vez. LiveKit está ouvindo…");
    });
  }

  function removeAudioElements() {
    stopBrowserSpeech();
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
      await window.__adaStopBrowserVoice?.();

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
            stt_received: message.message || "Transcrição recebida. Enviando ao Gemma 4…",
            stt_timeout: "Detectei sua voz, mas a transcrição falhou. Verifique a etapa de reconhecimento.",
            llm_started: "Sua fala chegou ao Gemma 4; gerando resposta…",
            agent_thinking: "A ADA-M está processando sua mensagem…",
            agent_speaking: "Resposta pronta; enviando para a voz do navegador…",
            agent_listening: "ADA-M pronta para ouvir.",
            assistant_text_ready: "A resposta textual da ADA-M foi gerada. Preparando a voz…",
            session_error: message.message || "A sessão de voz encontrou um erro."
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

      activeRoom.registerTextStreamHandler("lk.transcription", async (reader, participantInfo) => {
        try {
          const text = await reader.readAll();
          const attributes = reader.info?.attributes || {};
          const isTranscription = Boolean(attributes["lk.transcribed_track_id"]);
          
          // Ignora a transcrição da fala do usuário; só reproduz o texto produzido pelo agente.
          if (isTranscription || participantInfo?.identity === activeRoom.localParticipant.identity || !text.trim()) return;
          console.info("ADA-M LiveKit: resposta textual recebida para voz do navegador");
          statusLabel.dataset.diagnosticStage = "browser_tts";
          speakWithBrowserVoice(text);
        } catch (error) {
          console.warn("ADA-M LiveKit: falha ao receber texto da resposta", error);
          setStatus("Não consegui receber o texto da resposta do agente.");
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
          setStatus("A ADA-M está respondendo…");
        } else if (speakers.some((speaker) => speaker.identity === activeRoom.localParticipant.identity)) {
          setStatus("Sua voz foi detectada pelo LiveKit; aguardando transcrição…");
        }
      });

      // O agente não publica faixa de áudio: a resposta chega como texto e é falada pelo navegador.

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
      if (remoteAgent) {
        setStatus("Agente conectado. Microfone LiveKit ativo; pode falar.");
      } else {
        setStatus("Microfone ativo, mas aguardando o agente LiveKit. Se não conectar, confira o deploy do agente.");
      }
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
  if ("speechSynthesis" in window) window.speechSynthesis.getVoices();
  window.addEventListener("beforeunload", () => {
    try { room?.disconnect(); } catch {}
  });
}
