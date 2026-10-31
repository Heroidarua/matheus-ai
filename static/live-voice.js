(() => {
  const button = document.getElementById('voice-button');
  const status = document.getElementById('voice-status');
  const messages = document.getElementById('messages');
  if (!button || !status || !messages) return;
  const MAX_SESSION_MS = 5 * 60 * 1000;
  const IDLE_TIMEOUT_MS = 90 * 1000;
  let peer = null, channel = null, microphone = null, audioOutput = null;
  let active = false, connecting = false, transcriptSegments = [], lastConsumedEnd = 0;
  let liveHistory = [], delegationCounter = 0, maxTimer = null, idleTimer = null;
  const setStatus = value => { status.textContent = value; };
  const setButton = () => {
    button.classList.toggle('voice-active', active || connecting);
    button.setAttribute('aria-pressed', String(active || connecting));
    button.setAttribute('aria-label', active ? 'Encerrar GPT-Live' : 'Iniciar GPT-Live');
    button.title = active ? 'Encerrar GPT-Live' : 'Iniciar GPT-Live';
  };
  function addBubble(text, role, error = false) {
    document.getElementById('welcome')?.remove();
    const bubble = document.createElement('div');
    bubble.className = 'bubble ' + (role === 'user' ? 'user' : 'assistant') + (error ? ' error' : '');
    bubble.textContent = text; messages.appendChild(bubble);
    bubble.scrollIntoView({ behavior: 'smooth', block: 'end' }); return bubble;
  }
  function waitForIceGathering(connection) {
    if (connection.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise(resolve => {
      const timeout = setTimeout(resolve, 10000);
      connection.addEventListener('icegatheringstatechange', () => {
        if (connection.iceGatheringState === 'complete') { clearTimeout(timeout); resolve(); }
      });
    });
  }
  function sendEvent(event) { if (channel?.readyState === 'open') channel.send(JSON.stringify(event)); }
  function resetIdleTimer() {
    clearTimeout(idleTimer);
    if (active) idleTimer = setTimeout(() => stop('Live encerrado por 90 segundos sem fala para evitar uso contínuo.'), IDLE_TIMEOUT_MS);
  }
  function clearSafetyTimers() { clearTimeout(maxTimer); clearTimeout(idleTimer); maxTimer = null; idleTimer = null; }
  async function processDelegation(delegationId, offsetMs) {
    resetIdleTimer();
    const eligible = transcriptSegments.filter(s => s.endMs > lastConsumedEnd && s.endMs <= (Number(offsetMs) || Infinity) + 1500);
    const selected = eligible.length ? eligible : transcriptSegments.filter(s => s.endMs > lastConsumedEnd);
    const utterance = selected.map(s => s.text).join('').trim();
    if (selected.length) lastConsumedEnd = Math.max(lastConsumedEnd, ...selected.map(s => s.endMs));
    if (!utterance) {
      sendEvent({ type: 'session.commentary.append', event_id: 'live_no_transcript_' + (++delegationCounter), delegation_id: delegationId, content: 'Não consegui identificar sua última frase. Peça ao usuário para repetir.' });
      return;
    }
    addBubble(utterance, 'user'); liveHistory.push({ role: 'user', content: utterance }); liveHistory = liveHistory.slice(-12);
    setStatus('ADA-M está analisando sua solicitação…');
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ messages: liveHistory, mode: 'livre', response_length: 'curta', web_search: false, stream: false })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'O backend da ADA-M não conseguiu responder.');
      const answer = String(data.reply || '').trim(); if (!answer) throw new Error('O backend não retornou uma resposta.');
      liveHistory.push({ role: 'assistant', content: answer }); liveHistory = liveHistory.slice(-12);
      addBubble(answer, 'assistant');
      const spokenResult = answer.length > 1700 ? answer.slice(0, 1690).replace(/\\s+\\S*$/, '') + '…' : answer;
      sendEvent({ type: 'session.commentary.append', event_id: 'live_result_' + (++delegationCounter), delegation_id: delegationId, content: spokenResult });
      setStatus('Conversa ao vivo · pode continuar falando');
      resetIdleTimer();
    } catch (error) {
      addBubble('Não consegui concluir: ' + (error.message || 'Falha no backend.'), 'assistant', true);
      sendEvent({ type: 'session.commentary.append', event_id: 'live_error_' + (++delegationCounter), delegation_id: delegationId, content: 'Tive um problema ao consultar o sistema principal. Informe isso ao usuário sem inventar uma resposta.' });
      setStatus('Falha ao consultar ADA-M');
    }
  }
  function handleServerEvent(event) {
    if (!event || typeof event.type !== 'string') return;
    if (event.type === 'session.started') { active = true; connecting = false; setButton(); setStatus('GPT-Live conectado · limite de 5 minutos'); resetIdleTimer(); }
    else if (event.type === 'session.input_transcript.delta') {
      const text = String(event.delta || '');
      if (text) {
        resetIdleTimer();
        const startMs = Number(event.start_ms) || 0, endMs = Number(event.end_ms) || startMs;
        const previous = transcriptSegments[transcriptSegments.length - 1];
        if (previous && previous.startMs === startMs) { previous.text += text; previous.endMs = Math.max(previous.endMs, endMs); }
        else transcriptSegments.push({ startMs, endMs, text });
      }
    } else if (event.type === 'session.delegation.created' && event.delegation?.target === 'client') {
      processDelegation(event.delegation.id, event.offset_ms);
    } else if (event.type === 'session.usage.updated') {
      const seconds = Number(event.usage?.seconds);
      if (Number.isFinite(seconds) && seconds >= 300) stop('Live encerrado ao atingir o limite de 5 minutos.');
    } else if (event.type === 'error') {
      setStatus('GPT-Live: ' + (event.error?.message || event.message || 'erro na sessão'));
    } else if (event.type === 'session.closed') stop('Sessão encerrada.', false);
  }
  async function start() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) throw new Error('GPT-Live precisa de HTTPS e de um navegador com suporte a microfone/WebRTC.');
    connecting = true; setButton(); setStatus('Solicitando acesso ao microfone…');
    microphone = await navigator.mediaDevices.getUserMedia({ audio: true });
    peer = new RTCPeerConnection(); audioOutput = new Audio(); audioOutput.autoplay = true; audioOutput.playsInline = true;
    peer.ontrack = event => { audioOutput.srcObject = event.streams[0] || new MediaStream([event.track]); audioOutput.play().catch(() => setStatus('Toque na página para permitir a reprodução do áudio.')); };
    microphone.getTracks().forEach(track => peer.addTrack(track, microphone));
    channel = peer.createDataChannel('oai-events');
    channel.addEventListener('open', () => setStatus('Canal de voz conectado…'));
    channel.addEventListener('message', event => { try { handleServerEvent(JSON.parse(event.data)); } catch {} });
    const offer = await peer.createOffer(); await peer.setLocalDescription(offer); await waitForIceGathering(peer);
    setStatus('Conectando ao GPT-Live…');
    const response = await fetch('/api/live/session', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify({ sdp: peer.localDescription?.sdp || offer.sdp }) });
    const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || 'Não foi possível iniciar o GPT-Live.');
    maxTimer = setTimeout(() => stop('Live encerrado ao atingir o limite de 5 minutos.'), MAX_SESSION_MS);
    await peer.setRemoteDescription({ type: 'answer', sdp: data.sdp });
    active = true; connecting = false; setButton();
    setStatus('Finalizando conexão de áudio…');
  }
  function stop(message = 'Conversa GPT-Live encerrada.', notifyServer = true) {
    clearSafetyTimers();
    const oldChannel = channel, oldPeer = peer, oldMicrophone = microphone, oldAudioOutput = audioOutput;
    active = false; connecting = false;
    if (notifyServer && oldChannel?.readyState === 'open') {
      try { oldChannel.send(JSON.stringify({ type: 'session.close' })); } catch {}
      setButton(); setStatus(message);
      setTimeout(() => releaseConnection(oldChannel, oldPeer, oldMicrophone, oldAudioOutput), 1200);
      return;
    }
    releaseConnection(oldChannel, oldPeer, oldMicrophone, oldAudioOutput);
    setButton(); setStatus(message);
  }
  function releaseConnection(oldChannel, oldPeer, oldMicrophone, oldAudioOutput) {
    if (oldChannel) { try { oldChannel.close(); } catch {} }
    if (oldPeer) { try { oldPeer.close(); } catch {} }
    if (oldMicrophone) oldMicrophone.getTracks().forEach(track => track.stop());
    if (oldAudioOutput) { oldAudioOutput.pause(); oldAudioOutput.srcObject = null; }
    if (channel === oldChannel) channel = null;
    if (peer === oldPeer) peer = null;
    if (microphone === oldMicrophone) microphone = null;
    if (audioOutput === oldAudioOutput) audioOutput = null;
    transcriptSegments = []; lastConsumedEnd = 0;
  }
  async function toggle() {
    if (active || connecting) { stop(); return; }
    try { await start(); } catch (error) { stop('Falha ao iniciar GPT-Live.'); addBubble('Não foi possível iniciar o modo Live: ' + (error.message || 'erro desconhecido'), 'assistant', true); }
  }
  window.ADALiveVoice = { toggle, stop, get active() { return active; } }; setButton();
})();