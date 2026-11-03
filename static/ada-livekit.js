// Conversa por voz nativa do navegador.
// Mantém o botão existente, mas não abre sala LiveKit nem captura áudio via WebRTC.
// Entrada: SpeechRecognition do navegador. Resposta: /api/chat (Gemma 4) + SpeechSynthesis.
const startButton = document.getElementById("livekit-voice-button");
const statusLabel = document.getElementById("livekit-voice-status");

if (startButton && statusLabel) {
  let active = false;

  function renderState(isActive, message) {
    active = isActive;
    startButton.disabled = false;
    startButton.classList.toggle("livekit-active", isActive);
    startButton.textContent = isActive
      ? "⏹ Encerrar conversa"
      : "🎙️ Conversar por voz (navegador)";
    statusLabel.textContent = message;
  }

  startButton.addEventListener("click", () => {
    if (active) {
      window.__adaEndBrowserVoiceSession?.();
      renderState(false, "Conversa por voz encerrada.");
      return;
    }

    startButton.disabled = true;
    statusLabel.textContent = "Ativando o microfone do navegador…";
    const started = window.__adaStartBrowserVoiceSession?.();
    if (started) {
      renderState(true, "Voz do navegador ativa. Pode falar.");
    } else {
      renderState(false, "Não foi possível iniciar. Verifique o suporte e a permissão do microfone.");
    }
  });

  window.addEventListener("ada-browser-voice-ended", () => {
    renderState(false, "Conversa por voz encerrada.");
  });
}
