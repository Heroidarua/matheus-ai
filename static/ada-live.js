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

  let socket = null;
  let stream = null;
  let audioContext = null;
  let processor = null;
  let source = null;
  let mutedGain = null;
  let connecting = false;
  let active = false;
  let playbackGeneration = 0;
  let playbackAbort = null;
  let activeAudio = null;
  let activeAudioUrl = null;

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

  function speechParts(value) {
    const clean = String(value || '').replace(/https?:\/\/\S+/g, 'link').replace(/\s+/g, ' ').trim();
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
    const generation = playbackGeneration;
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
  }

  window.__adaLiveActive = false;
  window.__adaLiveOnResponse = async text => {
    if (!active) return;
    setLiveCaption(text);
    await speakWithTinyVoca(text);
  };

  function downsampleTo16k(input, inputRate) {
    if (inputRate === 16000) {
      const direct = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const sample = Math.max(-1, Math.min(1, input[i]));
        direct[i] = sample < 0 ? sample * 32768 : sample * 32767;
      }
      return direct;
    }
    const ratio = inputRate / 16000;
    const outputLength = Math.floor(input.length / ratio);
    const output = new Int16Array(outputLength);
    for (let i = 0; i < outputLength; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.min(Math.floor((i + 1) * ratio), input.length);
      let sum = 0;
      for (let j = start; j < end; j++) sum += input[j];
      const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
      output[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    return output;
  }

  async function startMicrophone() {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    await audioContext.resume();
    source = audioContext.createMediaStreamSource(stream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    mutedGain = audioContext.createGain();
    mutedGain.gain.value = 0;
    processor.onaudioprocess = event => {
      if (!active || !socket || socket.readyState !== WebSocket.OPEN) return;
      const input = event.inputBuffer.getChannelData(0);
      let energy = 0;
      for (let i = 0; i < input.length; i++) energy += input[i] * input[i];
      const rms = Math.sqrt(energy / Math.max(1, input.length));
      if (rms > 0.035 && (activeAudio || playbackAbort)) {
        stopPlayback();
        setStatus('Interrompida. Estou ouvindo você…');
      }
      const pcm = downsampleTo16k(input, audioContext.sampleRate);
      if (pcm.length) socket.send(pcm.buffer);
    };
    source.connect(processor);
    processor.connect(mutedGain);
    mutedGain.connect(audioContext.destination);
  }

  async function cleanup(message = 'Modo Live encerrado.', visible = false) {
    active = false;
    window.__adaLiveActive = false;
    stopPlayback();
    if (processor) {
      processor.onaudioprocess = null;
      try { processor.disconnect(); } catch (_) {}
      processor = null;
    }
    if (source) {
      try { source.disconnect(); } catch (_) {}
      source = null;
    }
    if (mutedGain) {
      try { mutedGain.disconnect(); } catch (_) {}
      mutedGain = null;
    }
    if (audioContext) {
      try { await audioContext.close(); } catch (_) {}
      audioContext = null;
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    if (socket) {
      const old = socket;
      socket = null;
      try { old.close(); } catch (_) {}
    }
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
    setStatus('Conectando diretamente à VPS…');
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Este navegador não liberou o acesso ao microfone.');
      await window.__adaStopBrowserVoice?.();
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(scheme + '//' + location.host + '/api/live/ws');
      socket.binaryType = 'arraybuffer';
      let resolveReady;
      let rejectReady;
      const readyPromise = new Promise((resolve, reject) => {
        resolveReady = resolve;
        rejectReady = reject;
      });
      socket.addEventListener('message', event => {
        let data;
        try { data = JSON.parse(event.data); } catch (_) { return; }
        if (data.type === 'status') setStatus(data.message);
        if (data.type === 'ready') {
          setStatus('Reconhecimento PT-BR pronto. Ativando microfone…');
          resolveReady();
        } else if (data.type === 'partial') {
          setStatus('Estou ouvindo você…');
          setLiveCaption(data.text || 'Estou ouvindo você…');
        } else if (data.type === 'transcript' && data.text) {
          setLiveCaption('Você: ' + data.text);
          setStatus('Entendi. Preparando resposta…');
          if (typeof window.__adaLiveSubmitTranscript === 'function') {
            window.__adaLiveSubmitTranscript(data.text);
          } else {
            prompt.value = data.text;
            form.requestSubmit();
          }
        } else if (data.type === 'error') {
          const message = data.message || 'Falha no reconhecimento de voz.';
          rejectReady(new Error(message));
          cleanup(message, true);
        }
      });
      socket.addEventListener('close', () => {
        if (active) cleanup('Conexão com a VPS encerrada.', true);
        else rejectReady(new Error('A VPS encerrou a conexão antes de ficar pronta.'));
      });
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Tempo esgotado ao conectar à VPS.')), 15000);
        socket.addEventListener('open', () => { clearTimeout(timeout); resolve(); }, { once: true });
        socket.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('Não foi possível conectar ao WebSocket da VPS.')); }, { once: true });
      });
      await Promise.race([
        readyPromise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('O reconhecimento de voz da VPS demorou demais para iniciar.')), 45000))
      ]);
      await startMicrophone();
      active = true;
      window.__adaLiveActive = true;
      button.disabled = false;
      button.classList.add('livekit-active');
      button.textContent = 'Encerrar Live';
      button.setAttribute('aria-label', 'Encerrar conversa ao vivo');
      setStatus('Conectada à VPS. Pode falar comigo…');
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
    try { socket?.close(); } catch (_) {}
    stream?.getTracks().forEach(track => track.stop());
  });
})();
