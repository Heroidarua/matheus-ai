(() => {
  'use strict';
  const dialog = document.getElementById('music-dialog');
  if (!dialog) return;
  const $ = id => document.getElementById(id);
  const status = $('music-status'), resultsEl = $('music-results'), stage = $('music-stage');
  const queryInput = $('music-query'), urlInput = $('music-url'), queueLabel = $('music-queue');
  const dock = $('music-mini-player'), dockStage = $('music-mini-stage'), dockTitle = $('music-mini-title');
  const modalBody = dialog.querySelector('.music-body'), modalControls = $('music-controls');
  let queue = [], queueIndex = -1, ytPlayer = null, ytApiPromise = null, playerCounter = 0;
  function hasTrack() { return !!(ytPlayer && queueIndex >= 0 && queue[queueIndex]); }
  function moveStageToDock() {
    if (!hasTrack() || dialog.open) return;
    if (stage.parentElement !== dockStage) dockStage.appendChild(stage);
    dock.hidden = false;
  }
  function moveStageToDialog() {
    if (stage.parentElement !== modalBody) modalBody.insertBefore(stage, modalControls);
    dock.hidden = true;
  }
  function updateMiniTitle(item) {
    if (dockTitle) dockTitle.textContent = item?.title || 'YouTube';
    updateMediaSession(item);
  }
  function updateMediaSession(item) {
    if (!('mediaSession' in navigator)) return;
    try {
      if ('MediaMetadata' in window) {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: item?.title || 'YouTube',
          artist: item?.channel || 'ADA-M Music',
          album: 'ADA-M',
          artwork: item?.thumbnail ? [{ src: item.thumbnail, sizes: '480x360', type: 'image/jpeg' }] : []
        });
      }
    } catch {}
  }
  function setMediaPlaybackState(state) {
    if (!('mediaSession' in navigator)) return;
    try { navigator.mediaSession.playbackState = state; } catch {}
  }
  function registerMediaSessionActions() {
    if (!('mediaSession' in navigator) || typeof navigator.mediaSession.setActionHandler !== 'function') return;
    const actions = {
      play: () => control('play'),
      pause: () => control('pause'),
      nexttrack: () => next(),
      previoustrack: () => previous(),
      stop: () => control('pause')
    };
    for (const [action, handler] of Object.entries(actions)) {
      try { navigator.mediaSession.setActionHandler(action, handler); } catch {}
    }
  }
  function say(message) { status.textContent = message; }
  function open() { moveStageToDialog(); if (!dialog.open) dialog.showModal(); setTimeout(() => queryInput?.focus(), 80); }
  function updateQueue() { queueLabel.textContent = queue.length ? ('Lista: ' + (queueIndex + 1) + '/' + queue.length) : 'Nenhuma música selecionada'; }
  function clearStage() {
    if (ytPlayer) { try { ytPlayer.destroy(); } catch {} ytPlayer = null; }
    stage.replaceChildren();
  }
  function makeButton(label, action, className = 'music-result-button') {
    const button = document.createElement('button'); button.type = 'button'; button.className = className;
    button.textContent = label; button.addEventListener('click', action); return button;
  }
  function loadYouTubeApi() {
    if (window.YT?.Player) return Promise.resolve(window.YT);
    if (ytApiPromise) return ytApiPromise;
    ytApiPromise = new Promise((resolve, reject) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { try { if (typeof previous === 'function') previous(); } catch {} resolve(window.YT); };
      let script = document.querySelector('script[src="https://www.youtube.com/iframe_api"]');
      if (!script) {
        script = document.createElement('script'); script.src = 'https://www.youtube.com/iframe_api'; script.async = true;
        script.onerror = () => reject(new Error('Não foi possível carregar o player oficial do YouTube.'));
        document.head.appendChild(script);
      }
    }).catch(error => { ytApiPromise = null; throw error; });
    return ytApiPromise;
  }
  async function showYouTube(item, autoplay = false) {
    clearStage();
    const target = document.createElement('div'); target.id = 'ada-m-youtube-player-' + (++playerCounter);
    target.style.width = '100%'; target.style.minHeight = '315px'; stage.appendChild(target);
    say('Carregando o player oficial do YouTube…'); updateQueue(); updateMiniTitle(item);
    try {
      const YT = await loadYouTubeApi();
      if (!stage.contains(target)) return;
      ytPlayer = new YT.Player(target.id, {
        width: '100%', height: '315', videoId: item.id,
        playerVars: { autoplay: autoplay ? 1 : 0, controls: 1, rel: 0, playsinline: 1, origin: location.origin },
        events: {
          onReady: () => { say('YouTube pronto: ' + (item.title || 'música selecionada') + '.'); if (!dialog.open) moveStageToDock(); },
          onStateChange: event => {
            if (event.data === YT.PlayerState.PLAYING) setMediaPlaybackState('playing');
            else if (event.data === YT.PlayerState.PAUSED) setMediaPlaybackState('paused');
            else if (event.data === YT.PlayerState.ENDED) setMediaPlaybackState('none');
            if (event.data === YT.PlayerState.ENDED && queueIndex >= 0 && queueIndex < queue.length - 1) {
              queueIndex++; showYouTube(queue[queueIndex], true);
            }
          },
          onError: event => {
            const reasons = { 2: 'Link ou ID do vídeo inválido.', 5: 'Este vídeo não pode ser reproduzido neste player HTML5.', 100: 'Este vídeo não está disponível.', 101: 'O proprietário não permite a reprodução incorporada deste vídeo.', 150: 'O proprietário não permite a reprodução incorporada deste vídeo.' };
            say(reasons[event.data] || 'O YouTube não conseguiu reproduzir este vídeo. Escolha outro resultado.');
          }
        }
      });
    } catch (error) { say(error.message || 'Falha ao iniciar o player do YouTube.'); }
  }
  function renderResults(items) {
    resultsEl.replaceChildren();
    if (!items.length) { const empty = document.createElement('p'); empty.className = 'music-empty'; empty.textContent = 'Nenhum resultado encontrado.'; resultsEl.appendChild(empty); return; }
    items.forEach((item, index) => {
      const row = document.createElement('div'); row.className = 'music-result';
      if (item.thumbnail) { const img = document.createElement('img'); img.src = item.thumbnail; img.alt = ''; img.loading = 'lazy'; row.appendChild(img); }
      const copy = document.createElement('div'); copy.className = 'music-result-copy';
      const title = document.createElement('strong'); title.textContent = item.title;
      const channel = document.createElement('small'); channel.textContent = item.channel || 'YouTube';
      copy.append(title, channel); row.appendChild(copy);
      row.appendChild(makeButton('▶ Tocar', () => { queue = items; queueIndex = index; showYouTube(item, true); }));
      resultsEl.appendChild(row);
    });
  }
  async function searchYouTube(query) {
    const clean = String(query || '').trim();
    if (clean.length < 2) { say('Digite o nome de uma música ou artista.'); return; }
    open(); queryInput.value = clean; say('Pesquisando no YouTube…'); resultsEl.replaceChildren();
    try {
      const response = await fetch('/api/music/youtube/search?q=' + encodeURIComponent(clean), { headers: { Accept: 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 503) {
          const link = document.createElement('a'); link.href = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(clean);
          link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'Abrir resultados no YouTube ↗'; link.style.color = 'var(--accent)';
          resultsEl.replaceChildren(link); say('Configure YOUTUBE_API_KEY no Render para mostrar os resultados dentro do ADA-M.'); return;
        }
        throw new Error(data.detail || 'A pesquisa no YouTube falhou.');
      }
      const items = Array.isArray(data.items) ? data.items : [];
      queue = items; queueIndex = -1; renderResults(items); updateQueue();
      say(items.length + ' resultado(s). Escolha uma música para reproduzir.');
    } catch (error) { say(error.message || 'Não foi possível pesquisar no YouTube.'); }
  }
  function parseYouTubeUrl(raw) {
    let url; try { url = new URL(String(raw || '').trim()); } catch { return null; }
    const host = url.hostname.replace(/^www\./, '').toLowerCase();
    if (host === 'youtu.be') { const id = url.pathname.split('/').filter(Boolean)[0]; return id ? { id } : null; }
    if (host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtube-nocookie.com') {
      const id = url.searchParams.get('v') || url.pathname.match(/\/(?:embed|shorts|live)\/([^/?]+)/)?.[1]; return id ? { id } : null;
    }
    return null;
  }
  function loadUrl(raw) {
    const parsed = parseYouTubeUrl(raw);
    if (!parsed) { say('Cole um link válido de vídeo, Shorts ou transmissão do YouTube.'); return; }
    queue = [{ id: parsed.id, title: 'Vídeo do YouTube' }]; queueIndex = 0; open(); showYouTube(queue[0], false);
  }
  function next() {
    if (queueIndex >= 0 && queueIndex < queue.length - 1) { queueIndex++; showYouTube(queue[queueIndex], true); }
    else say('Não há próxima música na lista.');
  }
  function previous() {
    if (queueIndex > 0) { queueIndex--; showYouTube(queue[queueIndex], true); }
    else if (ytPlayer?.seekTo) ytPlayer.seekTo(0, true);
    else say('Não há música anterior na lista.');
  }
  function control(action) {
    if (!ytPlayer) { say('Escolha uma música primeiro.'); return true; }
    try {
      if (action === 'pause') ytPlayer.pauseVideo();
      if (action === 'play') ytPlayer.playVideo();
      if (action === 'next') next();
      if (action === 'previous') previous();
    } catch { say('O player ainda está carregando. Tente novamente em instantes.'); }
    return true;
  }
  function handleCommand(raw) {
    const normalized = String(raw || '').trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/^ada[- ]?m[, ]*/, '').trim();
    if (!normalized) return false;
    if (/^(?:abra|abrir|abre|acessar|acesse|ir para|va para)\s+(?:o\s+)?youtube(?:\s+music)?$/i.test(normalized)) {
      open(); say('YouTube aberto no ADA-M. Pesquise uma música ou artista e escolha um resultado.'); return true;
    }
    const youtubeSearch = normalized.match(/^(?:abra|abrir|abre|pesquise|pesquisar|procure|buscar|busque)(?:\s+o)?\s+youtube(?:\s+e)?\s+(?:pesquise|pesquisar|procure|buscar|busque)\s+(.+)$/i);
    if (youtubeSearch) { searchYouTube(youtubeSearch[1].replace(/[.!?]+$/, '')); return true; }
    if (/\b(pausar|pause|pausa|pare a musica|parar musica|parar a musica)\b/.test(normalized)) { open(); control('pause'); return true; }
    if (/\b(continuar|continue|retomar|despausar|voltar a tocar|reproduzir novamente)\b/.test(normalized)) { open(); control('play'); return true; }
    if (/\b(proxima musica|proximo|seguinte|pule a musica|pular)\b/.test(normalized)) { open(); control('next'); return true; }
    if (/\b(musica anterior|voltar uma musica|anterior)\b/.test(normalized)) { open(); control('previous'); return true; }
    const volume = normalized.match(/\bvolume(?: para| em)?\s+(\d{1,3})\b/);
    if (volume) { if (ytPlayer?.setVolume) ytPlayer.setVolume(Math.max(0, Math.min(100, Number(volume[1])))); open(); say('Comando de volume enviado ao player do YouTube.'); return true; }
    const playMatch = normalized.match(/^(?:toque|toca|reproduza|reproduzir|coloque|coloca|bota|pesquise|procure)(?:\s+(?:a|uma|um))?\s+(?:(?:musica|som|faixa)\s+)?(?:de|do|da|dos|das)?\s*(.+)$/i);
    if (playMatch) { searchYouTube(playMatch[1].trim().replace(/[.!?]+$/, '')); return true; }
    if (/^(?:abra|abrir)\s+(?:o\s+)?(?:player|musica|music)$/i.test(normalized)) { open(); return true; }
    return false;
  }
  $('music-open').addEventListener('click', open);
  $('music-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', moveStageToDock);
  // Não pause nem destrua o iframe ao trocar de aba; mantenha o player fora do dialog.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && !dialog.open && hasTrack()) moveStageToDock();
  });
  registerMediaSessionActions();
  $('music-mini-expand').addEventListener('click', open);
  $('music-mini-hide').addEventListener('click', () => { dock.hidden = true; });
  $('music-mini-play').addEventListener('click', () => control('play'));
  $('music-mini-pause').addEventListener('click', () => control('pause'));
  $('music-mini-next').addEventListener('click', next);
  $('music-search').addEventListener('click', () => searchYouTube(queryInput.value));
  queryInput.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); searchYouTube(queryInput.value); } });
  $('music-load-url').addEventListener('click', () => loadUrl(urlInput.value));
  urlInput.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); loadUrl(urlInput.value); } });
  $('music-youtube-search').addEventListener('click', () => {
    const url = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(queryInput.value.trim());
    window.open(url, '_blank', 'noopener,noreferrer');
  });
  $('music-prev').addEventListener('click', previous);
  $('music-next').addEventListener('click', next);
  $('music-pause').addEventListener('click', () => control('pause'));
  $('music-play').addEventListener('click', () => control('play'));
  $('music-stop').addEventListener('click', () => {
    clearStage(); dock.hidden = true; setMediaPlaybackState('none');
    if ('mediaSession' in navigator) { try { navigator.mediaSession.metadata = null; } catch {} }
    say('Reprodução encerrada.'); updateQueue();
  });
  window.ADAMusic = { handleCommand, open, search: searchYouTube, loadUrl, control };
  const form = document.getElementById('chat-form'), prompt = document.getElementById('prompt');
  if (form && prompt) form.addEventListener('submit', event => {
    if (!handleCommand(prompt.value)) return;
    event.preventDefault(); event.stopImmediatePropagation(); prompt.value = ''; prompt.style.height = 'auto';
    window.dispatchEvent(new Event('ada-m:music-command-complete'));
  }, true);
})();