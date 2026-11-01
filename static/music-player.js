(() => {
  'use strict';
  const dialog = document.getElementById('music-dialog');
  if (!dialog) return;
  const $ = id => document.getElementById(id);
  const status = $('music-status');
  const resultsEl = $('music-results');
  const stage = $('music-stage');
  const queryInput = $('music-query');
  const urlInput = $('music-url');
  const fileInput = $('music-files');
  const queueLabel = $('music-queue');
  let queue = [];
  let queueIndex = -1;
  let audio = null;
  let objectUrls = [];
  let provider = '';
  let ytPlayerReady = false;

  function say(message) { status.textContent = message; }
  function open() { if (!dialog.open) dialog.showModal(); }
  function clearStage() {
    if (audio) { audio.pause(); audio.src = ''; audio = null; }
    stage.replaceChildren();
    provider = '';
  }
  function makeButton(label, action, className = 'music-result-button') {
    const button = document.createElement('button');
    button.type = 'button'; button.className = className; button.textContent = label;
    button.addEventListener('click', action);
    return button;
  }
  function showYouTube(item, autoplay = false) {
    clearStage();
    provider = 'youtube';
    const frame = document.createElement('iframe');
    frame.title = 'Reprodutor do YouTube';
    frame.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(item.id) +
      '?autoplay=' + (autoplay ? '1' : '0') + '&controls=1&rel=0&playsinline=1&enablejsapi=1&origin=' + encodeURIComponent(location.origin);
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.allowFullscreen = true;
    stage.appendChild(frame);
    say('YouTube: ' + item.title + (autoplay ? ' — se o navegador bloquear o início automático, toque em reproduzir.' : ''));
    updateQueue();
  }
  function updateQueue() {
    queueLabel.textContent = queue.length ? ('Fila: ' + (queueIndex + 1) + '/' + queue.length) : 'Nenhuma fila local';
  }
  function renderResults(items) {
    resultsEl.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p'); empty.className = 'music-empty';
      empty.textContent = 'Nenhum resultado encontrado.'; resultsEl.appendChild(empty); return;
    }
    items.forEach((item, index) => {
      const row = document.createElement('div'); row.className = 'music-result';
      if (item.thumbnail) {
        const img = document.createElement('img'); img.src = item.thumbnail; img.alt = ''; img.loading = 'lazy'; row.appendChild(img);
      }
      const copy = document.createElement('div'); copy.className = 'music-result-copy';
      const title = document.createElement('strong'); title.textContent = item.title;
      const channel = document.createElement('small'); channel.textContent = item.channel || 'YouTube';
      copy.append(title, channel);
      row.appendChild(copy);
      row.appendChild(makeButton('▶ Tocar', () => {
        queue = items; queueIndex = index; showYouTube(item, true);
      }));
      resultsEl.appendChild(row);
    });
  }
  function showExternalProvider(providerName, query = '') {
    open();
    resultsEl.replaceChildren();
    const isSpotify = providerName === 'spotify';
    const url = query
      ? (isSpotify ? 'https://open.spotify.com/search/' + encodeURIComponent(query) : 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query))
      : (isSpotify ? 'https://open.spotify.com/' : 'https://www.youtube.com/');
    const button = makeButton(isSpotify ? 'Abrir Spotify para escolher' : 'Abrir YouTube para escolher', () => {
      const opened = window.open(url, '_blank', 'noopener,noreferrer');
      if (!opened) say('O navegador bloqueou a nova aba. Permita pop-ups ou use o link abaixo.');
    });
    resultsEl.appendChild(button);
    const link = document.createElement('a');
    link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = isSpotify ? 'Abrir Spotify ↗' : 'Abrir YouTube ↗';
    link.style.color = 'var(--accent)';
    resultsEl.appendChild(link);
    say(query ? 'Escolha uma música nos resultados. A página será aberta em outra aba.' : 'Escolha uma música no serviço. A página será aberta em outra aba.');
  }
  async function searchYouTube(query, autoplayFirst = false) {
    open(); say('Pesquisando no YouTube…'); resultsEl.replaceChildren();
    try {
      const response = await fetch('/api/music/youtube/search?q=' + encodeURIComponent(query), { headers: { Accept: 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 503) {
          say('Pesquisa automática do YouTube ainda não configurada. Abra os resultados pelo link abaixo e cole um link de vídeo para reproduzir.');
          const link = document.createElement('a');
          link.href = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query);
          link.target = '_blank'; link.rel = 'noopener noreferrer';
          link.textContent = 'Abrir resultados no YouTube ↗';
          link.style.color = 'var(--accent)';
          resultsEl.replaceChildren(link);
          return;
        }
        throw new Error(data.detail || 'A pesquisa no YouTube falhou.');
      }
      const items = Array.isArray(data.items) ? data.items : [];
      queue = items; queueIndex = items.length ? 0 : -1;
      renderResults(items);
      if (items.length && autoplayFirst) showYouTube(items[0], true);
      else say(items.length + ' resultado(s) do YouTube. Escolha uma faixa para tocar.');
    } catch (error) { say(error.message || 'Não foi possível pesquisar no YouTube.'); }
  }
  function parseProviderUrl(raw) {
    let url;
    try { url = new URL(raw.trim()); } catch { return null; }
    const host = url.hostname.replace(/^www\./, '').toLowerCase();
    if (host === 'youtu.be') {
      const id = url.pathname.split('/').filter(Boolean)[0];
      return id ? { provider: 'youtube', id } : null;
    }
    if (host.endsWith('youtube.com') || host === 'youtube-nocookie.com') {
      const id = url.searchParams.get('v') || url.pathname.match(/\/(?:embed|shorts|live)\/([^/?]+)/)?.[1];
      return id ? { provider: 'youtube', id } : null;
    }
    if (host === 'open.spotify.com' || host === 'spotify.link') {
      const match = url.pathname.match(/\/(track|album|playlist|episode|show)\/([A-Za-z0-9]+)/);
      return match ? { provider: 'spotify', type: match[1], id: match[2] } : null;
    }
    return null;
  }
  function loadUrl(raw) {
    const parsed = parseProviderUrl(raw);
    if (!parsed) { say('Cole um link válido de vídeo do YouTube ou faixa, álbum ou playlist do Spotify.'); return; }
    open(); clearStage();
    if (parsed.provider === 'youtube') {
      showYouTube({ id: parsed.id, title: 'Vídeo do YouTube' }, false);
    } else {
      provider = 'spotify';
      const frame = document.createElement('iframe');
      frame.title = 'Reprodutor do Spotify';
      frame.src = 'https://open.spotify.com/embed/' + parsed.type + '/' + parsed.id + '?utm_source=generator&theme=0';
      frame.width = '100%'; frame.height = '352'; frame.allow = 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture';
      frame.loading = 'lazy'; frame.style.border = '0'; frame.style.borderRadius = '12px';
      stage.appendChild(frame);
      say('Spotify conectado pelo player oficial. A disponibilidade depende da faixa, região e tipo de conta.');
    }
  }
  function playLocal(index) {
    if (!queue.length || index < 0 || index >= queue.length) return;
    queueIndex = index; clearStage(); provider = 'local';
    const item = queue[index];
    audio = document.createElement('audio');
    audio.controls = true; audio.autoplay = true; audio.preload = 'metadata'; audio.src = item.url;
    audio.addEventListener('ended', () => { if (queueIndex < queue.length - 1) playLocal(queueIndex + 1); });
    stage.appendChild(audio);
    const name = document.createElement('div'); name.className = 'music-now-playing'; name.textContent = '♫ ' + item.name;
    stage.appendChild(name);
    audio.play().catch(() => say('Arquivo carregado. Toque em reproduzir no controle de áudio.'));
    say('Reproduzindo arquivo local: ' + item.name);
    updateQueue();
  }
  function next() {
    if (provider === 'local' && queueIndex < queue.length - 1) playLocal(queueIndex + 1);
    else if (provider === 'youtube' && queueIndex < queue.length - 1) { queueIndex++; showYouTube(queue[queueIndex], true); }
    else say('Não há próxima faixa na fila.');
  }
  function previous() {
    if (provider === 'local' && queueIndex > 0) playLocal(queueIndex - 1);
    else if (provider === 'youtube' && queueIndex > 0) { queueIndex--; showYouTube(queue[queueIndex], true); }
    else if (provider === 'local' && audio) audio.currentTime = 0;
    else say('Não há faixa anterior na fila.');
  }
  function control(action) {
    if (provider === 'local' && audio) {
      if (action === 'pause') audio.pause();
      if (action === 'play') audio.play().catch(() => {});
      if (action === 'next') next();
      if (action === 'previous') previous();
      return true;
    }
    if (provider === 'youtube') {
      const frame = stage.querySelector('iframe');
      if (frame?.contentWindow) {
        const command = action === 'pause' ? 'pauseVideo' : action === 'play' ? 'playVideo' : null;
        if (command) frame.contentWindow.postMessage(JSON.stringify({ event: 'command', func: command, args: [] }), '*');
        if (action === 'next') next();
        if (action === 'previous') previous();
        return true;
      }
    }
    if (provider === 'spotify') {
      say('Use os controles dentro do player do Spotify para essa ação.');
      return true;
    }
    say('Abra uma música primeiro para usar os controles.');
    return true;
  }
  function handleCommand(raw) {
    const text = String(raw || '').trim();
    if (!text) return false;
    const normalized = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/^ada[- ]?m[, ]*/, '').trim();
    if (/\b(pausar|pause|pausa|pare a musica|parar musica|parar a musica)\b/.test(normalized)) {
      open(); control('pause'); say('Música pausada.'); return true;
    }
    if (/\b(continuar|continue|retomar|despausar|voltar a tocar|reproduzir novamente)\b/.test(normalized)) {
      open(); control('play'); say('Continuando a reprodução.'); return true;
    }
    if (/\b(proxima musica|proximo|seguinte|pule a musica|pular)\b/.test(normalized)) { open(); control('next'); return true; }
    if (/\b(musica anterior|voltar uma musica|anterior)\b/.test(normalized)) { open(); control('previous'); return true; }
    const volume = normalized.match(/\bvolume(?: para| em)?\s+(\d{1,3})\b/);
    if (volume) {
      const value = Math.max(0, Math.min(100, Number(volume[1])));
      if (audio) audio.volume = value / 100;
      if (provider === 'youtube') {
        const frame = stage.querySelector('iframe');
        frame?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func: 'setVolume', args: [value] }), '*');
      }
      open();
      say(provider === 'spotify' ? 'Ajuste o volume pelo player do Spotify ou pelo dispositivo.' : 'Comando de volume enviado ao player.');
      return true;
    }
    const providerCommand = normalized.match(/^(?:abra|abrir|abre|acessar|acesse|ir para|va para)\s+(?:o\s+|a\s+)?(youtube|youtube music|spotify)(?:\s+(?:e\s+)?(?:pesquise|procure|busque)\s+(.+))?$/i);
    if (providerCommand) {
      const service = providerCommand[1].includes('spotify') ? 'spotify' : 'youtube';
      showExternalProvider(service, (providerCommand[2] || '').trim().replace(/[.!?]+$/, ''));
      return true;
    }
    const playMatch = normalized.match(/^(?:toque|toca|reproduza|reproduzir|coloque|coloca|bota|pesquise|procure)(?:\s+(?:a|uma|um))?\s+(?:(?:musica|som|faixa)\s+)?(?:de|do|da|dos|das)?\s*(.+)$/i);
    if (playMatch) {
      const query = playMatch[1].trim().replace(/[.!?]+$/, '');
      if (query.length < 2) return false;
      queryInput.value = query;
      searchYouTube(query, true);
      return true;
    }
    if (/^(?:abra|abrir)\s+(?:o\s+)?(?:player|musica|music)$/i.test(normalized)) { open(); return true; }
    return false;
  }

  $('music-open').addEventListener('click', open);
  $('music-close').addEventListener('click', () => dialog.close());
  $('music-search').addEventListener('click', () => {
    const query = queryInput.value.trim();
    if (query) searchYouTube(query, false); else say('Digite o nome de uma música ou artista.');
  });
  queryInput.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); $('music-search').click(); } });
  $('music-load-url').addEventListener('click', () => loadUrl(urlInput.value));
  urlInput.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); loadUrl(urlInput.value); } });
  $('music-youtube-search').addEventListener('click', () => showExternalProvider('youtube', queryInput.value.trim()));
  $('music-spotify-search').addEventListener('click', () => showExternalProvider('spotify', queryInput.value.trim()));
  $('music-local-button').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (!fileInput.files?.length) return;
    objectUrls.forEach(url => URL.revokeObjectURL(url)); objectUrls = [];
    queue = Array.from(fileInput.files).filter(file => file.type.startsWith('audio/')).map(file => {
      const url = URL.createObjectURL(file); objectUrls.push(url); return { name: file.name, url };
    });
    queueIndex = queue.length ? 0 : -1;
    if (queue.length) playLocal(0); else say('Nenhum arquivo de áudio compatível foi selecionado.');
    fileInput.value = '';
  });
  $('music-prev').addEventListener('click', previous);
  $('music-next').addEventListener('click', next);
  $('music-pause').addEventListener('click', () => control('pause'));
  $('music-play').addEventListener('click', () => control('play'));
  $('music-stop').addEventListener('click', () => { clearStage(); say('Reprodução encerrada.'); updateQueue(); });
  window.addEventListener('beforeunload', () => objectUrls.forEach(url => URL.revokeObjectURL(url)));

  window.ADAMusic = { handleCommand, open, search: searchYouTube, loadUrl, control };
  const form = document.getElementById('chat-form');
  const prompt = document.getElementById('prompt');
  if (form && prompt) {
    form.addEventListener('submit', event => {
      if (!handleCommand(prompt.value)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      prompt.value = '';
      prompt.style.height = 'auto';
      window.dispatchEvent(new Event('ada-m:music-command-complete'));
    }, true);
  }
})();