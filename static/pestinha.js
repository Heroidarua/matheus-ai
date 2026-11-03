(() => {
  'use strict';

  // Companheiro visual independente para a ADA-M, inspirado no conceito de pet virtual.
  // Não monitora janelas, teclado global ou outros aplicativos. Os dados ficam no navegador.
  if (window.__adaPestinhaInitialized) return;
  window.__adaPestinhaInitialized = true;

  const style = document.createElement('style');
  style.textContent = `
    #ada-pestinha { position:fixed; z-index:40; right:18px; bottom:108px; display:flex; flex-direction:column; align-items:flex-end; gap:8px; font-family:Inter,ui-sans-serif,system-ui,sans-serif; pointer-events:none; }
    #ada-pestinha * { box-sizing:border-box; }
    #ada-pestinha .pet-bubble { max-width:min(250px,calc(100vw - 36px)); padding:9px 12px; border:1px solid var(--border,#424242); border-radius:14px 14px 4px 14px; background:var(--panel,#2f2f2f); color:var(--text,#ececec); box-shadow:0 8px 28px #0005; font-size:12px; line-height:1.45; opacity:0; transform:translateY(6px) scale(.97); transition:opacity .18s ease,transform .18s ease; pointer-events:none; }
    #ada-pestinha.show-message .pet-bubble { opacity:1; transform:translateY(0) scale(1); }
    #ada-pestinha .pet-row { display:flex; align-items:flex-end; gap:8px; pointer-events:auto; }
    #ada-pestinha .pet-character { width:76px; height:76px; padding:0; border:0; border-radius:50%; background:transparent; cursor:pointer; filter:drop-shadow(0 7px 10px #0007); touch-action:manipulation; }
    #ada-pestinha .pet-character:focus-visible { outline:2px solid var(--accent,#10a37f); outline-offset:4px; }
    #ada-pestinha .pet-character svg { width:100%; height:100%; overflow:visible; }
    #ada-pestinha .pet-body { transform-origin:50% 85%; animation:adaPetFloat 3s ease-in-out infinite; }
    #ada-pestinha .pet-eyes { transform-origin:center; animation:adaPetBlink 5.2s infinite; }
    #ada-pestinha[data-mood="happy"] .pet-body { animation:adaPetHappy .55s ease-in-out 2; }
    #ada-pestinha[data-mood="thinking"] .pet-eyes { animation:adaPetThink .8s ease-in-out infinite alternate; }
    #ada-pestinha[data-mood="sleepy"] .pet-eyes { transform:scaleY(.22); animation:none; }
    #ada-pestinha[data-mood="curious"] .pet-body { transform:rotate(-5deg); }
    #ada-pestinha .pet-shadow { transform-origin:center; animation:adaPetShadow 3s ease-in-out infinite; }
    #ada-pestinha .pet-close { width:25px; height:25px; margin-bottom:5px; border:1px solid var(--border,#424242); border-radius:50%; background:var(--panel,#2f2f2f); color:var(--muted,#aaa); cursor:pointer; font-size:15px; line-height:1; }
    #ada-pestinha .pet-caption { color:var(--muted,#aaa); font-size:10px; text-align:right; padding-right:4px; }
    @keyframes adaPetFloat { 0%,100%{transform:translateY(0) rotate(0)} 50%{transform:translateY(-7px) rotate(2deg)} }
    @keyframes adaPetShadow { 0%,100%{transform:scaleX(1);opacity:.22} 50%{transform:scaleX(.78);opacity:.12} }
    @keyframes adaPetBlink { 0%,43%,47%,100%{transform:scaleY(1)} 45%{transform:scaleY(.12)} }
    @keyframes adaPetHappy { 0%,100%{transform:translateY(0) rotate(0)} 30%{transform:translateY(-13px) rotate(-8deg)} 65%{transform:translateY(-5px) rotate(7deg)} }
    @keyframes adaPetThink { from{transform:translateY(0)} to{transform:translateY(-2px)} }
    @media(max-width:520px){ #ada-pestinha{right:10px;bottom:116px;} #ada-pestinha .pet-character{width:64px;height:64px;} #ada-pestinha .pet-bubble{font-size:11px;} }
    @media(prefers-reduced-motion:reduce){ #ada-pestinha *,#ada-pestinha *::before{animation:none!important;transition:none!important;} }
  `;
  document.head.appendChild(style);

  const root = document.createElement('aside');
  root.id = 'ada-pestinha';
  root.dataset.mood = 'idle';
  root.setAttribute('aria-label', 'Pestinha, bichinho virtual da ADA-M');
  root.innerHTML = `
    <div class="pet-bubble" role="status" aria-live="polite">Oi! Vou ficar aqui fazendo companhia. 🐾</div>
    <div class="pet-row">
      <button class="pet-close" type="button" aria-label="Ocultar mensagem">×</button>
      <button class="pet-character" type="button" aria-label="Fazer carinho no Pestinha" title="Faça carinho no bichinho">
        <svg viewBox="0 0 100 100" role="img" aria-hidden="true">
          <ellipse class="pet-shadow" cx="50" cy="88" rx="25" ry="5" fill="#000"/>
          <g class="pet-body">
            <path d="M17 57 C12 36 25 17 49 14 C73 11 88 31 84 55 C82 72 70 83 51 84 C31 85 20 74 17 57Z" fill="#75e6c5" stroke="#b5ffe9" stroke-width="2"/>
            <path d="M24 32 Q12 18 31 22 Q38 24 40 30" fill="#75e6c5" stroke="#b5ffe9" stroke-width="2"/>
            <path d="M61 29 Q75 14 80 28 Q81 34 72 37" fill="#75e6c5" stroke="#b5ffe9" stroke-width="2"/>
            <ellipse cx="50" cy="56" rx="27" ry="23" fill="#a8f5dd" opacity=".55"/>
            <g class="pet-eyes" fill="#143b35">
              <ellipse cx="39" cy="49" rx="3.7" ry="5.3"/>
              <ellipse cx="62" cy="49" rx="3.7" ry="5.3"/>
            </g>
            <path d="M46 61 Q51 66 57 61" fill="none" stroke="#24594d" stroke-width="2.5" stroke-linecap="round"/>
            <circle cx="30" cy="60" r="4" fill="#ff9eaa" opacity=".7"/>
            <circle cx="70" cy="60" r="4" fill="#ff9eaa" opacity=".7"/>
            <path d="M34 81 Q30 89 23 86 M65 82 Q71 89 78 85" fill="none" stroke="#75e6c5" stroke-width="5" stroke-linecap="round"/>
            <path d="M77 43 Q91 35 88 25" fill="none" stroke="#b5ffe9" stroke-width="3" stroke-linecap="round"/>
          </g>
          <circle cx="73" cy="18" r="5" fill="#ffe28a"><animate attributeName="opacity" values=".3;1;.3" dur="2.4s" repeatCount="indefinite"/></circle>
        </svg>
      </button>
    </div>
    <div class="pet-caption">Pestinha da ADA-M</div>
  `;
  document.body.appendChild(root);

  const bubble = root.querySelector('.pet-bubble');
  const petButton = root.querySelector('.pet-character');
  const closeButton = root.querySelector('.pet-close');
  const form = document.querySelector('form');
  const sendButton = document.getElementById('send');
  const prompt = document.getElementById('prompt');
  const messages = document.getElementById('messages');

  const phrases = {
    idle: ['Estou de olho… quer dizer, de olhinhos! 👀', 'Só observando o movimento por aqui.', 'Um carinho seria muito bem-vindo. 🐾'],
    curious: ['Opa! O que vamos aprontar agora?', 'Isso parece interessante…', 'Fiquei curioso!'],
    thinking: ['A ADA-M está pensando… 🤔', 'Processando junto com a minha humana favorita!', 'Hmm… neurônios trabalhando!'],
    happy: ['Eba! Mais uma conversa! 💚', 'Adorei essa interação!', 'Pulinhos de felicidade!'],
    sleepy: ['Zzz… pode me chamar quando precisar.']
  };
  const state = { mood: 'idle', affection: 0, timer: 0 };
  try {
    const saved = JSON.parse(localStorage.getItem('ada-pestinha-state') || '{}');
    state.affection = Math.max(0, Math.min(999, Number(saved.affection) || 0));
  } catch {}

  function setMood(mood, message, duration = 3200) {
    state.mood = mood;
    root.dataset.mood = mood;
    if (message) {
      bubble.textContent = message;
      root.classList.add('show-message');
    }
    clearTimeout(state.timer);
    if (duration > 0) {
      state.timer = setTimeout(() => {
        root.dataset.mood = 'idle';
        state.mood = 'idle';
        root.classList.remove('show-message');
      }, duration);
    }
  }

  function save() {
    try { localStorage.setItem('ada-pestinha-state', JSON.stringify({ affection: state.affection })); } catch {}
  }

  petButton.addEventListener('click', () => {
    state.affection = Math.min(999, state.affection + 1);
    save();
    const lines = ['Hehe! Gostei do carinho! 💚', 'Mais um carinho, por favor!', 'Você ganhou +1 ponto de amizade!'];
    setMood('happy', lines[Math.floor(Math.random() * lines.length)]);
  });
  closeButton.addEventListener('click', () => root.classList.remove('show-message'));

  if (prompt) {
    prompt.addEventListener('input', () => {
      if (prompt.value.trim() && state.mood !== 'thinking') {
        setMood('curious', 'Está escrevendo algo para mim ou para a ADA-M?');
      }
    });
  }
  if (form) {
    form.addEventListener('submit', () => {
      if (prompt && prompt.value.trim()) setMood('curious', 'Mensagem enviada! Vamos ver…', 1800);
    }, true);
  }
  if (sendButton) {
    const observer = new MutationObserver(() => {
      if (sendButton.disabled) setMood('thinking', 'A ADA-M está preparando a resposta…', 0);
      else if (state.mood === 'thinking') setMood('happy', 'Chegou resposta! ✨', 4200);
    });
    observer.observe(sendButton, { attributes: true, attributeFilter: ['disabled'] });
  }
  if (messages) {
    const observer = new MutationObserver(records => {
      const added = records.some(record => [...record.addedNodes].some(node =>
        node.nodeType === 1 && (node.classList?.contains('assistant') || node.classList?.contains('user') || node.querySelector?.('.assistant,.user'))
      ));
      if (added && sendButton && !sendButton.disabled && state.mood !== 'thinking') {
        setMood('happy', 'Estamos fazendo um bom trabalho juntos! 💚');
      }
    });
    observer.observe(messages, { childList: true, subtree: true });
  }

  // A cada intervalo longo, o pet descansa visualmente sem recolher a interface.
  let idleTimer = setTimeout(() => setMood('sleepy', 'Zzz… estou tirando uma sonequinha.', 5200), 180000);
  ['pointerdown', 'keydown', 'touchstart'].forEach(eventName => {
    window.addEventListener(eventName, () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => setMood('sleepy', 'Zzz… estou tirando uma sonequinha.', 5200), 180000);
    }, { passive: true });
  });
})();
