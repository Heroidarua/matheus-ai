(() => {
  'use strict';
  const voiceButton = document.getElementById('voice-live-button');
  const voiceStatus = document.getElementById('voice-status');
  const sendButton = document.getElementById('send');
  const stopButton = document.getElementById('stop-button');
  if (!voiceButton || !voiceStatus || document.getElementById('ada-m-live')) return;

  const style = document.createElement('style');
  style.textContent = `
    #ada-m-live{position:fixed;inset:0;z-index:9998;display:grid;grid-template-rows:auto 1fr auto;align-items:center;justify-items:center;padding:calc(22px + env(safe-area-inset-top)) 22px calc(24px + env(safe-area-inset-bottom));background:radial-gradient(ellipse at 50% 43%,rgba(40,110,96,.2),transparent 44%),rgba(4,7,8,.97);backdrop-filter:blur(18px);color:#f5f7f7;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .22s ease,visibility .22s ease}
    #ada-m-live.is-open{opacity:1;visibility:visible;pointer-events:auto}
    #ada-m-live .live-top{width:min(100%,560px);display:flex;align-items:center;justify-content:space-between}
    #ada-m-live .live-brand{display:flex;align-items:center;gap:10px;font:650 14px/1.2 Inter,system-ui,sans-serif;letter-spacing:.12em}
    #ada-m-live .live-brand-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:#70e1c1;color:#071b18;font-size:23px;font-weight:800;letter-spacing:0}
    #ada-m-live button{font:600 13px Inter,system-ui,sans-serif;cursor:pointer}
    #ada-m-live .live-close{width:42px;height:42px;border-radius:50%;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.06);color:#fff;font-size:22px}
    #ada-m-live .live-center{display:grid;justify-items:center;gap:30px;text-align:center;align-self:center;margin-top:-3vh}
    #ada-m-live .live-orb-wrap{position:relative;width:min(66vw,290px);height:min(66vw,290px);display:grid;place-items:center}
    #ada-m-live .live-orb-halo{position:absolute;inset:4%;border-radius:50%;background:conic-gradient(from 20deg,rgba(112,225,193,.02),rgba(112,225,193,.24),rgba(98,166,255,.18),rgba(112,225,193,.02));filter:blur(14px);animation:adaLiveRotate 12s linear infinite}
    #ada-m-live .live-orb{position:relative;width:72%;height:72%;border-radius:50%;background:radial-gradient(circle at 34% 27%,#d8fff3 0,#79e8ce 9%,#239c87 34%,#123c3b 68%,#071c20 100%);box-shadow:inset -18px -20px 38px rgba(0,0,0,.48),inset 9px 9px 22px rgba(255,255,255,.35),0 0 42px rgba(70,205,177,.3),0 0 100px rgba(42,157,140,.16);animation:adaLiveFloat 4s ease-in-out infinite}
    #ada-m-live .live-orb:before,#ada-m-live .live-orb:after{content:"";position:absolute;inset:12%;border-radius:50%;border:1px solid rgba(222,255,248,.22);transform:rotate(-25deg) scaleY(.48)}
    #ada-m-live .live-orb:after{inset:4% 19%;transform:rotate(35deg) scaleY(.7);border-color:rgba(151,255,229,.16)}
    #ada-m-live[data-state="listening"] .live-orb{animation:adaLiveListen 2.1s ease-in-out infinite}
    #ada-m-live[data-state="speaking"] .live-orb{animation:adaLiveSpeak 1.05s ease-in-out infinite}
    #ada-m-live[data-state="thinking"] .live-orb{animation:adaLiveThink 2.4s ease-in-out infinite}
    #ada-m-live .live-title{margin:0;font:600 clamp(22px,5vw,30px)/1.2 Inter,system-ui,sans-serif;letter-spacing:-.04em}
    #ada-m-live .live-caption{margin:9px 0 0;color:rgba(235,245,242,.66);font:400 14px/1.5 Inter,system-ui,sans-serif;min-height:22px}
    #ada-m-live .live-bottom{display:grid;justify-items:center;gap:17px;width:min(100%,560px)}
    #ada-m-live .live-controls{display:flex;align-items:center;gap:14px}
    #ada-m-live .live-control{min-width:58px;height:58px;padding:0 18px;border-radius:30px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.08);color:#fff}
    #ada-m-live .live-control.primary{background:#70e1c1;color:#061a17;border-color:#70e1c1;min-width:68px;font-size:19px}
    #ada-m-live .live-hint{color:rgba(235,245,242,.42);font:400 11px/1.4 Inter,system-ui,sans-serif;text-align:center}
    @keyframes adaLiveRotate{to{transform:rotate(360deg)}}
    @keyframes adaLiveFloat{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-7px) scale(1.025)}}
    @keyframes adaLiveListen{0%,100%{transform:scale(.96);box-shadow:inset -18px -20px 38px rgba(0,0,0,.48),0 0 35px rgba(70,205,177,.28)}50%{transform:scale(1.04);box-shadow:inset -18px -20px 38px rgba(0,0,0,.48),0 0 65px rgba(70,205,177,.5)}}
    @keyframes adaLiveSpeak{0%,100%{transform:scale(.98)}50%{transform:scale(1.09)}}
    @keyframes adaLiveThink{0%,100%{transform:rotate(0) scale(.96)}50%{transform:rotate(8deg) scale(1.02)}}
    @media(prefers-reduced-motion:reduce){#ada-m-live *,#ada-m-live *:before,#ada-m-live *:after{animation:none!important;transition:none!important}}
  `;
  document.head.appendChild(style);

  const overlay = document.createElement('section');
  overlay.id = 'ada-m-live';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Conversa por voz ADA-M Live');
  overlay.dataset.state = 'listening';
  overlay.innerHTML = `
    <div class="live-top">
      <div class="live-brand"><span class="live-brand-mark">+</span><span>ADA-M LIVE</span></div>
      <button class="live-close" type="button" aria-label="Encerrar conversa por voz">×</button>
    </div>
    <div class="live-center">
      <div class="live-orb-wrap" aria-hidden="true"><div class="live-orb-halo"></div><div class="live-orb"></div></div>
      <div><h2 class="live-title">Estou aqui com você.</h2><p class="live-caption" aria-live="polite">Preparando o microfone…</p></div>
    </div>
    <div class="live-bottom">
      <div class="live-controls">
        <button class="live-control" type="button" data-action="stop" aria-label="Interromper resposta">■</button>
        <button class="live-control primary" type="button" data-action="end" aria-label="Encerrar conversa">×</button>
      </div>
      <div class="live-hint">Fale naturalmente. Para encerrar, toque no botão ×.</div>
    </div>`;
  document.body.appendChild(overlay);

  const caption = overlay.querySelector('.live-caption');
  const title = overlay.querySelector('.live-title');
  const close = () => {
    if (voiceButton.classList.contains('voice-active')) voiceButton.click();
    else overlay.classList.remove('is-open');
  };
  overlay.querySelector('.live-close').addEventListener('click', close);
  overlay.querySelector('[data-action="end"]').addEventListener('click', close);
  overlay.querySelector('[data-action="stop"]').addEventListener('click', () => {
    stopButton?.click();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    caption.textContent = 'Resposta interrompida. Pode falar.';
    overlay.dataset.state = 'listening';
    title.textContent = 'Estou ouvindo você.';
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && overlay.classList.contains('is-open')) close();
  });

  function sync() {
    const active = voiceButton.classList.contains('voice-active');
    overlay.classList.toggle('is-open', active);
    if (!active) return;
    const status = (voiceStatus.textContent || '').trim();
    const lower = status.toLocaleLowerCase('pt-BR');
    const busy = !!sendButton?.disabled;
    if (busy || /analisando|processando|entendi:|executando|preparando/.test(lower)) {
      overlay.dataset.state = 'thinking';
      title.textContent = 'Deixe comigo.';
      caption.textContent = busy ? 'Estou preparando sua resposta…' : (status || 'Preparando…');
    } else if (/falando|respondendo|voz natural/.test(lower) || window.speechSynthesis?.speaking) {
      overlay.dataset.state = 'speaking';
      title.textContent = 'Estou falando com você.';
      caption.textContent = 'Pode me interromper quando quiser.';
    } else if (/interromp/.test(lower)) {
      overlay.dataset.state = 'listening';
      title.textContent = 'Pode continuar.';
      caption.textContent = status;
    } else {
      overlay.dataset.state = 'listening';
      title.textContent = 'Estou ouvindo você.';
      caption.textContent = status || 'Sua vez. Pode falar.';
    }
  }

  const observer = new MutationObserver(sync);
  observer.observe(voiceButton, { attributes: true, attributeFilter: ['class'] });
  observer.observe(voiceStatus, { childList: true, characterData: true, subtree: true });
  if (sendButton) observer.observe(sendButton, { attributes: true, attributeFilter: ['disabled'] });
  window.addEventListener('beforeunload', () => observer.disconnect(), { once: true });

  // Ajusta a fala nativa para priorizar vozes brasileiras instaladas e reduzir o ritmo robótico.
  if ('speechSynthesis' in window && !window.__adaSpeechNaturalized) {
    window.__adaSpeechNaturalized = true;
    const nativeSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
    const chooseNaturalVoice = () => {
      const voices = window.speechSynthesis.getVoices().filter(v => /^pt[-_]BR$/i.test(v.lang));
      const score = voice => {
        const name = (voice.name || '').toLocaleLowerCase('pt-BR');
        let points = voice.localService ? 12 : 0;
        if (/google/.test(name)) points += 24;
        if (/microsoft.*(francisca|fernanda|female)|francisca|fernanda|luciana/.test(name)) points += 20;
        if (/natural|neural|premium/.test(name)) points += 18;
        if (/portugu[eê]s.*brasil|brazilian portuguese/.test(name)) points += 8;
        if (/compact|e.?mail|espeak/.test(name)) points -= 20;
        return points;
      };
      return voices.sort((a,b) => score(b)-score(a))[0] || null;
    };
    window.speechSynthesis.speak = utterance => {
      if (utterance instanceof SpeechSynthesisUtterance) {
        utterance.lang = 'pt-BR';
        // Velocidade mais próxima de uma conversa natural, sem acelerar sílabas.
        utterance.rate = 1.20;
        utterance.pitch = 1.0;
        const preferred = chooseNaturalVoice();
        if (preferred) utterance.voice = preferred;
      }
      return nativeSpeak(utterance);
    };
  }


  // Mantém uma única sessão de reconhecimento durante a fala do usuário.
  // O Web Speech pode encerrar a sessão por conta própria; nesse caso, retoma
  // com atraso curto e sem criar instâncias concorrentes.
  let liveFinalTranscript = '';
  let liveFinalizeTimer = null;
  let liveRecognitionStarting = false;
  let liveRecognitionRetry = 0;

  function finalizeLiveUtterance() {
    clearTimeout(liveFinalizeTimer);
    const transcript = liveFinalTranscript.trim();
    liveFinalTranscript = '';
    if (!transcript || !voiceSessionActive || sendButton?.disabled) return;
    if (window.ADAMusic?.handleCommand(transcript)) {
      voiceStatus.textContent = 'Executando comando do YouTube…';
      window.dispatchEvent(new Event('ada-m:music-command-complete'));
      return;
    }
    promptEl.value = transcript;
    voiceStatus.textContent = 'Entendi: ' + transcript;
    stopVoiceRecognition();
    form.requestSubmit();
  }

  startVoiceRecognition = function startVoiceRecognitionStable() {
    if (!voiceSessionActive || !SpeechRecognitionAPI || sendButton?.disabled ||
        recognition || liveRecognitionStarting ||
        (window.speechSynthesis && (window.speechSynthesis.speaking || window.speechSynthesis.pending))) return;

    liveRecognitionStarting = true;
    const instance = new SpeechRecognitionAPI();
    recognition = instance;
    instance.lang = 'pt-BR';
    instance.continuous = true;
    instance.interimResults = true;
    instance.maxAlternatives = 1;

    instance.onstart = () => {
      liveRecognitionStarting = false;
      liveRecognitionRetry = 0;
      voiceStatus.textContent = 'Ouvindo você…';
    };

    instance.onresult = event => {
      if (!voiceSessionActive) return;
      let changed = false;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (!result?.isFinal) continue;
        const phrase = result[0]?.transcript?.trim();
        if (phrase) {
          liveFinalTranscript = [liveFinalTranscript, phrase].filter(Boolean).join(' ').trim();
          changed = true;
        }
      }
      if (changed) {
        clearTimeout(liveFinalizeTimer);
        liveFinalizeTimer = setTimeout(finalizeLiveUtterance, 950);
      }
    };

    instance.onerror = event => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        voiceSessionActive = false;
        voiceConversationToggle.checked = false;
        updateVoiceButton();
        voiceStatus.textContent = 'Permita o acesso ao microfone para conversar por voz.';
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        voiceStatus.textContent = 'Reconectando o microfone…';
      }
    };

    instance.onend = () => {
      if (recognition === instance) recognition = null;
      liveRecognitionStarting = false;
      if (!voiceSessionActive || sendButton?.disabled) return;
      if (liveFinalTranscript.trim()) {
        clearTimeout(liveFinalizeTimer);
        liveFinalizeTimer = setTimeout(finalizeLiveUtterance, 350);
        return;
      }
      liveRecognitionRetry = Math.min(liveRecognitionRetry + 1, 4);
      const delay = Math.min(450 * liveRecognitionRetry, 1400);
      clearTimeout(recognitionRestartTimer);
      recognitionRestartTimer = setTimeout(() => {
        if (voiceSessionActive && !recognition && !sendButton?.disabled) startVoiceRecognition();
      }, delay);
    };

    try {
      instance.start();
    } catch {
      if (recognition === instance) recognition = null;
      liveRecognitionStarting = false;
      if (voiceSessionActive) {
        clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = setTimeout(startVoiceRecognition, 900);
      }
    }
  };

  const originalStopVoiceRecognition = stopVoiceRecognition;
  stopVoiceRecognition = function stopVoiceRecognitionStable() {
    clearTimeout(liveFinalizeTimer);
    liveFinalTranscript = '';
    liveRecognitionStarting = false;
    originalStopVoiceRecognition();
  };

  const originalEndVoiceSession = endVoiceSession;
  endVoiceSession = function endVoiceSessionStable(message) {
    clearTimeout(liveFinalizeTimer);
    liveFinalTranscript = '';
    liveRecognitionStarting = false;
    originalEndVoiceSession(message);
  };

  sync();
})();