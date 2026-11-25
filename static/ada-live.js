(() => {
  const button = document.getElementById('livekit-voice-button');
  const status = document.getElementById('livekit-voice-status');
  const prompt = document.getElementById('prompt');
  const form = document.getElementById('chat-form');
  const liveOverlay = document.getElementById('live-experience');
  const liveOverlayStatus = document.getElementById('live-overlay-status');
  const liveCaption = document.getElementById('live-caption');
  const liveEndButton = document.getElementById('live-end-button');
  if (!button || !status || !prompt || !form || !liveOverlay || !liveOverlayStatus || !liveCaption || !liveEndButton) return;

  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let recognitionPaused = false;
  let recognitionRestartTimer = null;
  let connecting = false;
  let active = false;
  let playbackGeneration = 0;
  let playbackAbort = null;
  let activeAudio = null;
  let activeAudioUrl = null;
  let transcriptBuffer = [];
  let transcriptTimer = null;
  const transcriptPauseMs = 1600;

  function setStatus(message, visible = true) {
    status.textContent = message;
    status.hidden = !visible;
    liveOverlayStatus.textContent = message;
    if (/falando|preparando a voz/i.test(message)) liveOverlay.dataset.state = 'speaking';
    else if (/erro|falha|encerrada|não foi possível|tempo esgotado/i.test(message)) liveOverlay.dataset.state = 'error';
    else if (/ouvindo|sua vez|reconhecimento pt-br pronto|conectada à vps/i.test(message)) liveOverlay.dataset.state = 'listening';
    else liveOverlay.dataset.state = 'thinking';
  }

  function openLiveExperience() {
    liveOverlay.hidden = false;
    document.body.classList.add('live-experience-open');
    liveOverlay.setAttribute('aria-hidden', 'false');
    liveCaption.textContent = 'Estou pronta para conversar com você.';
    liveEndButton.focus({ preventScroll: true });
  }

  function closeLiveExperience() {
    liveOverlay.hidden = true;
    document.body.classList.remove('live-experience-open');
    liveOverlay.setAttribute('aria-hidden', 'true');
  }

  function clearTranscriptTimer() {
    if (transcriptTimer) {
      clearTimeout(transcriptTimer);
      transcriptTimer = null;
    }
  }

  function flushTranscriptBuffer() {
    clearTranscriptTimer();
    const transcript = transcriptBuffer.join(' ').replace(/\s+/g, ' ').trim();
    transcriptBuffer = [];
    if (!transcript || !active) return;
    setLiveCaption('Você: ' + transcript);
    setStatus('Entendi. Preparando resposta…');
    if (typeof window.__adaLiveSubmitTranscript === 'function') {
      window.__adaLiveSubmitTranscript(transcript);
    } else {
      prompt.value = transcript;
      form.requestSubmit();
    }
  }

  function queueTranscriptSegment(value) {
    const clean = String(value || '').replace(/\s+/g, ' ').trim();
    if (!clean) return;
    transcriptBuffer.push(clean);
    clearTranscriptTimer();
    transcriptTimer = setTimeout(flushTranscriptBuffer, transcriptPauseMs);
  }

  function setLiveCaption(value) {
    const clean = String(value || '').replace(/\s+/g, ' ').trim();
    if (clean) liveCaption.textContent = clean.length > 220 ? clean.slice(0, 217) + '…' : clean;
  }

  function stopPlayback() {
    playbackGeneration += 1;
    if (playbackAbort) {
      playbackAbort.abort();
      playbackAbort = null;
    }
    if (activeAudio) {
      const audio = activeAudio;
      activeAudio = null;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }
    if (activeAudioUrl) {
      URL.revokeObjectURL(activeAudioUrl);
      activeAudioUrl = null;
    }
  }

  // Sanitiza toda resposta antes de enviá-la ao Tiny-Voca.
  // A limpeza é aplicada no texto completo (inclusive pesquisas), antes de dividir em frases.
  function prepareLiveSpeechText(text) {
    let value = String(text || '').replace(/\r/g, '');

    // Não narrar blocos de código; manter o conteúdo de código inline sem os acentos.
    value = value.replace(/\x60{3}[\s\S]*?\x60{3}/g, ' trecho de código omitido ');
    value = value.replace(/\x60([^\x60]+)\x60/g, '$1');

    // Links/imagens: manter somente o rótulo, nunca a URL.
    value = value.replace(/!?\[([^\]]*)\]\(https?:\/\/[^\s)]+(?:\s+[^)]*)?\)/g, '$1');
    value = value.replace(/https?:\/\/[^\s)]+/g, ' ');

    // Não narrar a seção de referências nem os índices de citação.
    value = value.replace(/(?:^|\n)\s{0,3}(?:#{1,6}\s*)?[*_~]*\s*(?:fontes|sources|referências|referencias|bibliografia)\b[*_~]*\s*:?[ \t]*[\s\S]*$/i, ' ');
    value = value.replace(/(?:^|\n)\s*(?:fontes|sources|referências|referencias|bibliografia)\s*:\s*[\s\S]*$/i, ' ');
    value = value.replace(/\[(?:\d+\s*(?:,\s*\d+\s*)*)\]/g, ' ');

    // Remover cabeçalhos mesmo sem espaço após #, listas e citações.
    value = value.replace(/^\s{0,3}#{1,6}\s*/gm, '');
    value = value.replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/gm, '');
    value = value.replace(/^\s*>+\s?/gm, '');
    value = value.replace(/^\s*(?:[-*_]\s*){3,}$/gm, ' ');

    // Remover tags HTML, escapes e todos os delimitadores Markdown restantes.
    value = value.replace(/<[^>]*>/g, ' ');
    value = value.replace(/\\([*_#~\x60\[\](){}|>])/g, '$1');
    value = value.replace(/[*_#~\x60]/g, '');
    value = value.replace(/[\[\](){}]/g, '');
    value = value.replace(/\|/g, ', ');

    // Símbolos decorativos não devem ser pronunciados.
    value = value.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, ' ');
    return value.replace(/[ \t]+/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function speechParts(value) {
    const clean = prepareLiveSpeechText(value);
    if (!clean) return [];
    const sentences = clean.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) || [clean];
    const output = [];
    for (const sentence of sentences) {
      const part = sentence.trim();
      if (part.length <= 420) output.push(part);
      else output.push(...(part.match(/.{1,380}(?:[,;:]\s+|$)/g) || [part]).map(item => item.trim()).filter(Boolean));
    }
    return output;
  }

  async function speakWithTinyVoca(text) {
    stopPlayback();
    recognitionPaused = true;
    stopBrowserRecognition();
    const generation = playbackGeneration;
    try {
      for (const part of speechParts(text)) {
        if (!active || generation !== playbackGeneration) return;
        const controller = new AbortController();
        playbackAbort = controller;
        setStatus('ADA-M preparando a voz…');
        try {
          const response = await fetch('/api/tts/speech', {
            method: 'POST',
            credentials: 'same-origin',
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json', 'Accept': 'audio/wav' },
            body: JSON.stringify({ text: part, speed: 1.19 })
          });
          if (!response.ok) {
            let detail = 'Tiny-Voca não conseguiu gerar o áudio.';
            try { detail = (await response.json()).detail || detail; } catch (_) {}
            throw new Error(detail);
          }
          const blob = await response.blob();
          if (!blob.size || generation !== playbackGeneration || !active) return;
          activeAudioUrl = URL.createObjectURL(blob);
          const audio = new Audio(activeAudioUrl);
          activeAudio = audio;
          audio.preload = 'auto';
          setStatus('ADA-M falando…');
          await new Promise((resolve, reject) => {
            let settled = false;
            const finish = error => {
              if (settled) return;
              settled = true;
              audio.onended = null;
              audio.onerror = null;
              audio.onpause = null;
              error ? reject(error) : resolve();
            };
            audio.onended = () => finish();
            audio.onerror = () => finish(new Error('Falha ao reproduzir o áudio.'));
            audio.onpause = () => finish();
            audio.play().catch(finish);
          });
          if (activeAudio === audio) activeAudio = null;
          if (activeAudioUrl) {
            URL.revokeObjectURL(activeAudioUrl);
            activeAudioUrl = null;
          }
        } catch (error) {
          if (error.name === 'AbortError' || generation !== playbackGeneration) return;
          setStatus(error.message || 'Falha na reprodução da voz.');
          return;
        } finally {
          if (playbackAbort === controller) playbackAbort = null;
        }
      }
      if (active && generation === playbackGeneration) setStatus('Sua vez. Pode falar…');
    } finally {
      recognitionPaused = false;
      if (active) startBrowserRecognition();
    }
  }

  window.__adaLiveActive = false;
  window.__adaLiveOnResponse = async text => {
    if (!active) return;
    const speechText = prepareLiveSpeechText(text);
    if (!speechText) return;
    setLiveCaption(speechText);
    await speakWithTinyVoca(speechText);
  };


  function stopBrowserRecognition() {
    clearTimeout(recognitionRestartTimer);
    recognitionRestartTimer = null;
    if (!recognition) return;
    const current = recognition;
    recognition = null;
    try { current.stop(); } catch (_) {
      try { current.abort(); } catch (_) {}
    }
  }

  function startBrowserRecognition() {
    if (!active || recognitionPaused || activeAudio || playbackAbort || recognition) return;
    if (!SpeechRecognitionAPI) {
      setStatus('O reconhecimento de voz deste navegador não está disponível. Use Chrome ou Edge atualizado.', true);
      return;
    }

    const instance = new SpeechRecognitionAPI();
    recognition = instance;
    instance.lang = 'pt-BR';
    instance.continuous = true;
    instance.interimResults = true;
    instance.maxAlternatives = 1;

    instance.onstart = () => {
      if (active && !recognitionPaused) setStatus('Estou ouvindo você…');
    };

    instance.onresult = event => {
      if (!active || recognitionPaused) return;
      let interim = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const value = String(result[0]?.transcript || '').replace(/\\s+/g, ' ').trim();
        if (!value) continue;
        if (result.isFinal) {
          transcriptBuffer.push(value);
          clearTranscriptTimer();
          transcriptTimer = setTimeout(flushTranscriptBuffer, transcriptPauseMs);
        } else {
          interim += (interim ? ' ' : '') + value;
        }
      }

      if (interim) clearTranscriptTimer();
      const preview = [...transcriptBuffer, interim].join(' ').replace(/\\s+/g, ' ').trim();
      if (preview) setLiveCaption('Você: ' + preview);
      if (active && !recognitionPaused && !activeAudio && !playbackAbort) {
        setStatus('Estou ouvindo você…');
      }
    };

    instance.onerror = event => {
      if (!active || recognitionPaused || event.error === 'aborted' || event.error === 'no-speech') return;
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setStatus('Permita o acesso ao microfone para usar o reconhecimento de voz.', true);
        cleanup('Permissão do microfone negada.', true);
      } else {
        setStatus('O reconhecimento teve uma interrupção. Tentando novamente…');
      }
    };

    instance.onend = () => {
      if (recognition === instance) recognition = null;
      if (active && !recognitionPaused && !activeAudio && !playbackAbort) {
        clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = setTimeout(startBrowserRecognition, 350);
      }
    };

    try {
      instance.start();
    } catch (_) {
      if (recognition === instance) recognition = null;
      if (active && !recognitionPaused) {
        clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = setTimeout(startBrowserRecognition, 700);
      }
    }
  }

  async function cleanup(message = 'Modo Live encerrado.', visible = false) {
    active = false;
    recognitionPaused = true;
    clearTranscriptTimer();
    clearTimeout(recognitionRestartTimer);
    recognitionRestartTimer = null;
    transcriptBuffer = [];
    window.__adaLiveActive = false;
    stopBrowserRecognition();
    stopPlayback();
    button.disabled = false;
    button.classList.remove('livekit-active');
    button.textContent = '🎙️ Live';
    button.setAttribute('aria-label', 'Iniciar conversa ao vivo');
    closeLiveExperience();
    setStatus(message, visible);
  }

  async function connect() {
    if (connecting) return;
    if (active) {
      await cleanup();
      return;
    }
    connecting = true;
    button.disabled = true;
    openLiveExperience();
    setStatus('Preparando reconhecimento de voz do navegador…');
    try {
      if (!SpeechRecognitionAPI) {
        throw new Error('Este navegador não oferece reconhecimento de voz. Use Chrome ou Edge atualizado.');
      }
      await window.__adaStopBrowserVoice?.();
      active = true;
      window.__adaLiveActive = true;
      recognitionPaused = false;
      startBrowserRecognition();
      button.disabled = false;
      button.classList.add('livekit-active');
      button.textContent = 'Encerrar Live';
      button.setAttribute('aria-label', 'Encerrar conversa ao vivo');
      setStatus('Microfone conectado. Pode falar comigo…');
    } catch (error) {
      await cleanup(error.message || 'Falha ao iniciar o modo Live.', true);
    } finally {
      connecting = false;
      button.disabled = false;
    }
  }

  button.addEventListener('click', connect);
  liveEndButton.addEventListener('click', () => cleanup());
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !liveOverlay.hidden) cleanup();
  });
  window.addEventListener('beforeunload', () => {
    stopPlayback();
    try { recognition?.abort(); } catch (_) {}
  });
})();
