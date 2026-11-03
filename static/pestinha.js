(() => {
  'use strict';
  // Adaptação web isolada. O código desktop original permanece em vendor/pestinha.
  // Não monitora janelas, teclado global, processos ou outras abas.
  if (window.__adaPestinhaInitialized) return;
  window.__adaPestinhaInitialized = true;

  const ASSET = '/static/pestinha/pets/';
  const characters = {
    bryan: {
      name: 'Bryan', color: '#79e5b8', edge: '#c0ffe0', dark: '#153c31',
      phrases: {
        idle: ['E aí! O que vamos fazer hoje?', 'Estou de olho no chat. 👀', 'Um carinho não faz mal, né?'],
        curious: ['Opa, isso parece interessante!', 'O que será que vem agora?', 'Fiquei curioso com essa ideia.'],
        thinking: ['A ADA-M está pensando…', 'Hmm… deixa eu acompanhar esse raciocínio.', 'Neurônios trabalhando!'],
        happy: ['Aí sim! Gostei do carinho!', 'Eba! Mais uma missão!', 'Agora fiquei animado!'],
        sleepy: ['Zzz… só descansando os olhinhos.'],
        bravo: ['Ei! Calma com esse botão!']
      },
      memes: { happy:'bryan/memes/feliz/feliz_10.webp', curious:'bryan/memes/bravo/bravo_11.webp', bravo:'bryan/memes/bravo/bravo_12.webp', sleepy:'bryan/memes/triste/triste_29.webp', thinking:'bryan/memes/trabalhando/trabalho_20.webp' }
    },
    jorge: {
      name: 'Jorge', color: '#d9a83d', edge: '#ffe6a0', dark: '#17140d',
      phrases: {
        idle: ['Tenho uma mentoria… brincadeira! 😎', 'O mercado está de olho em você.', 'Vamos transformar ideias em… ideias!'],
        curious: ['Interessante. Isso pode virar um pitch!', 'Conte mais sobre essa oportunidade.', 'Estou analisando o potencial.'],
        thinking: ['Calculando o ROI imaginário…', 'Deixa eu preparar um slide mental.', 'Analisando o cenário de negócios.'],
        happy: ['Excelente! Um investimento em carinho!', 'Fechado! Mentoria de abraços liberada.', 'O valuation da amizade subiu!'],
        sleepy: ['Até coach precisa de uma pausa. Zzz…'],
        bravo: ['Isso não estava no meu pitch!']
      },
      memes: { happy:'jorge/memes/feliz/jorge_feliz_01.webp', curious:'jorge/memes/curioso/jorge_curioso_01.webp', bravo:'jorge/memes/bravo/jorge_bravo_01.webp', thinking:'jorge/memes/contente/jorge_contente_01.webp' }
    }
  };

  const style = document.createElement('style');
  style.textContent = "#ada-pestinha{position:fixed;z-index:40;right:20px;bottom:104px;width:238px;display:flex;flex-direction:column;align-items:stretch;gap:7px;font-family:Inter,ui-sans-serif,system-ui,sans-serif;pointer-events:none}#ada-pestinha *{box-sizing:border-box}#ada-pestinha .pet-top{display:flex;justify-content:flex-end;gap:5px;pointer-events:auto}#ada-pestinha .pet-choice,#ada-pestinha .pet-hide{border:1px solid var(--border,#333);background:var(--panel,#171717);color:var(--muted,#aaa);border-radius:999px;padding:5px 9px;font-size:10px;cursor:pointer}#ada-pestinha .pet-choice[aria-pressed=true]{color:var(--text,#fff);border-color:var(--pet-color,var(--accent));background:var(--panel2,#242424)}#ada-pestinha .pet-hide{width:25px;padding:0;font-size:15px}#ada-pestinha .pet-bubble{display:flex;align-items:center;gap:9px;min-height:52px;padding:9px 11px;border:1px solid var(--border,#333);border-radius:14px 14px 4px 14px;background:var(--panel,#171717);color:var(--text,#eee);box-shadow:0 8px 28px #0006;font-size:12px;line-height:1.4;opacity:0;transform:translateY(6px) scale(.98);transition:opacity .18s ease,transform .18s ease;pointer-events:none}#ada-pestinha.show-message .pet-bubble{opacity:1;transform:translateY(0) scale(1)}#ada-pestinha .pet-bubble img{width:54px;height:54px;object-fit:contain;border-radius:8px;flex:none}#ada-pestinha .pet-row{display:flex;align-items:flex-end;justify-content:flex-end;gap:8px;pointer-events:auto}#ada-pestinha .pet-character{width:88px;height:88px;padding:0;border:0;background:transparent;cursor:pointer;filter:drop-shadow(0 8px 10px #0007);touch-action:manipulation}#ada-pestinha .pet-character:focus-visible,#ada-pestinha button:focus-visible{outline:2px solid var(--pet-color,var(--accent));outline-offset:3px}#ada-pestinha .pet-character svg{width:100%;height:100%;overflow:visible}#ada-pestinha .pet-body{transform-origin:50% 85%;animation:adaPetFloat 3s ease-in-out infinite}#ada-pestinha .pet-eyes{transform-origin:center;animation:adaPetBlink 5.2s infinite}#ada-pestinha[data-mood=happy] .pet-body{animation:adaPetHappy .55s ease-in-out 2}#ada-pestinha[data-mood=thinking] .pet-eyes{animation:adaPetThink .8s ease-in-out infinite alternate}#ada-pestinha[data-mood=sleepy] .pet-eyes{transform:scaleY(.18);animation:none}#ada-pestinha[data-mood=curious] .pet-body{transform:rotate(-5deg)}#ada-pestinha .pet-shadow{transform-origin:center;animation:adaPetShadow 3s ease-in-out infinite}#ada-pestinha .pet-caption{color:var(--muted,#aaa);font-size:10px;text-align:right;padding-right:5px}#ada-pestinha .tie{display:none}#ada-pestinha[data-character=jorge] .tie{display:block}#ada-pestinha[data-character=jorge] .bryan-ear{display:none}@keyframes adaPetFloat{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-7px) rotate(2deg)}}@keyframes adaPetShadow{0%,100%{transform:scaleX(1);opacity:.22}50%{transform:scaleX(.78);opacity:.12}}@keyframes adaPetBlink{0%,43%,47%,100%{transform:scaleY(1)}45%{transform:scaleY(.12)}}@keyframes adaPetHappy{0%,100%{transform:translateY(0) rotate(0)}30%{transform:translateY(-13px) rotate(-8deg)}65%{transform:translateY(-5px) rotate(7deg)}}@keyframes adaPetThink{from{transform:translateY(0)}to{transform:translateY(-2px)}}@media(max-width:520px){#ada-pestinha{right:10px;bottom:112px;width:205px}#ada-pestinha .pet-character{width:72px;height:72px}#ada-pestinha .pet-bubble{font-size:11px}}@media(prefers-reduced-motion:reduce){#ada-pestinha *,#ada-pestinha *:before,#ada-pestinha *:after{animation:none!important;transition:none!important}}";
  document.head.appendChild(style);

  const root = document.createElement('aside');
  root.id = 'ada-pestinha';
  root.dataset.mood = 'idle';
  root.dataset.character = 'bryan';
  root.setAttribute('aria-label', 'Pestinha, companheiro virtual da ADA-M');
  root.innerHTML = [
    '<div class="pet-top"><button class="pet-choice" type="button" data-character="bryan" aria-pressed="true">Bryan</button><button class="pet-choice" type="button" data-character="jorge" aria-pressed="false">Jorge</button><button class="pet-hide" type="button" aria-label="Ocultar mensagens">×</button></div>',
    '<div class="pet-bubble" role="status" aria-live="polite"><span class="pet-message">Oi! Vou ficar aqui fazendo companhia. 🐾</span></div>',
    '<div class="pet-row"><button class="pet-character" type="button" aria-label="Fazer carinho em Bryan" title="Clique para fazer carinho"><svg viewBox="0 0 100 100" role="img" aria-hidden="true">',
    '<ellipse class="pet-shadow" cx="50" cy="89" rx="27" ry="5" fill="#000"/><g class="pet-body">',
    '<path d="M17 58C12 35 25 15 49 13C74 11 89 31 84 57C82 75 69 85 50 85C30 85 20 74 17 58Z" fill="var(--pet-color,#79e5b8)" stroke="var(--pet-edge,#c0ffe0)" stroke-width="2.4"/>',
    '<path class="bryan-ear" d="M25 31Q10 13 29 20Q37 23 40 31M62 29Q76 12 82 27Q83 34 72 38" fill="var(--pet-color)" stroke="var(--pet-edge)" stroke-width="2"/>',
    '<path d="M24 43Q50 25 77 43L75 65Q50 81 25 65Z" fill="#fff" opacity=".13"/><g class="pet-eyes" fill="var(--pet-dark,#153c31)"><ellipse cx="39" cy="49" rx="4" ry="5.7"/><ellipse cx="62" cy="49" rx="4" ry="5.7"/></g>',
    '<path d="M45 62Q51 68 58 61" fill="none" stroke="var(--pet-dark)" stroke-width="2.5" stroke-linecap="round"/><circle cx="29" cy="61" r="4.2" fill="#ff9eaa" opacity=".7"/><circle cx="71" cy="61" r="4.2" fill="#ff9eaa" opacity=".7"/>',
    '<path d="M35 82Q29 90 22 86M65 82Q72 90 79 85" fill="none" stroke="var(--pet-color)" stroke-width="5" stroke-linecap="round"/>',
    '<g class="tie"><path d="M46 73L54 73L57 80L50 87L43 80Z" fill="#b3261e" stroke="#ffe6a0" stroke-width="1"/><path d="M45 70H55L54 75H46Z" fill="#b3261e"/></g>',
    '<g fill="none" stroke="var(--pet-edge)" stroke-width="2" opacity=".95"><rect x="31" y="43" width="16" height="13" rx="4"/><rect x="54" y="43" width="16" height="13" rx="4"/><path d="M47 48H54M31 47L25 45M70 47L76 45"/></g></g>',
    '<circle cx="77" cy="18" r="4.5" fill="#ffe28a"><animate attributeName="opacity" values=".3;1;.3" dur="2.4s" repeatCount="indefinite"/></circle></svg></button></div>',
    '<div class="pet-caption">Pestinha • <span class="pet-name">Bryan</span></div>'
  ].join('');
  document.body.appendChild(root);

  const bubble = root.querySelector('.pet-bubble');
  const petButton = root.querySelector('.pet-character');
  const nameLabel = root.querySelector('.pet-name');
  const hideButton = root.querySelector('.pet-hide');
  const choices = [...root.querySelectorAll('.pet-choice')];
  const form = document.querySelector('form');
  const sendButton = document.getElementById('send');
  const prompt = document.getElementById('prompt');
  const messages = document.getElementById('messages');
  const state = { character: 'bryan', mood: 'idle', affection: 0, timer: 0, idleTimer: 0 };

  try {
    const saved = JSON.parse(localStorage.getItem('ada-pestinha-state') || '{}');
    if (characters[saved.character]) state.character = saved.character;
    state.affection = Math.max(0, Math.min(9999, Number(saved.affection) || 0));
  } catch {}

  function save() {
    try { localStorage.setItem('ada-pestinha-state', JSON.stringify({ character: state.character, affection: state.affection })); } catch {}
  }
  function phrase(mood) {
    const lines = characters[state.character].phrases[mood] || characters[state.character].phrases.idle;
    return lines[Math.floor(Math.random() * lines.length)];
  }
  function setMood(mood, text, duration = 3800) {
    state.mood = mood;
    root.dataset.mood = mood;
    const pet = characters[state.character];
    const meme = pet.memes[mood];
    const line = text || phrase(mood);
    if (meme) {
      bubble.innerHTML = '<img alt="" loading="lazy"><span class="pet-message"></span>';
      bubble.querySelector('img').src = ASSET + meme;
      bubble.querySelector('.pet-message').textContent = line;
    } else {
      bubble.textContent = line;
    }
    root.classList.add('show-message');
    clearTimeout(state.timer);
    if (duration > 0) state.timer = setTimeout(() => {
      state.mood = 'idle';
      root.dataset.mood = 'idle';
      root.classList.remove('show-message');
    }, duration);
  }
  function setCharacter(id) {
    if (!characters[id]) return;
    state.character = id;
    const pet = characters[id];
    root.dataset.character = id;
    root.style.setProperty('--pet-color', pet.color);
    root.style.setProperty('--pet-edge', pet.edge);
    root.style.setProperty('--pet-dark', pet.dark);
    nameLabel.textContent = pet.name;
    petButton.setAttribute('aria-label', 'Fazer carinho em ' + pet.name);
    choices.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.character === id)));
    save();
    setMood('idle', phrase('idle'));
  }

  choices.forEach(button => button.addEventListener('click', () => setCharacter(button.dataset.character)));
  petButton.addEventListener('click', () => {
    state.affection = Math.min(9999, state.affection + 1);
    save();
    setMood('happy', phrase('happy'));
  });
  hideButton.addEventListener('click', () => root.classList.remove('show-message'));
  if (prompt) prompt.addEventListener('input', () => {
    if (prompt.value.trim() && state.mood !== 'thinking') setMood('curious', phrase('curious'), 2600);
  });
  if (form) form.addEventListener('submit', () => {
    if (prompt && prompt.value.trim()) setMood('curious', 'Mensagem enviada! Vamos ver…', 1600);
  }, true);
  if (sendButton) {
    const observer = new MutationObserver(() => {
      if (sendButton.disabled) setMood('thinking', phrase('thinking'), 0);
      else if (state.mood === 'thinking') setMood('happy', 'A resposta chegou! ✨', 3600);
    });
    observer.observe(sendButton, { attributes: true, attributeFilter: ['disabled'] });
  }
  if (messages) {
    const observer = new MutationObserver(records => {
      const added = records.some(record => [...record.addedNodes].some(node =>
        node.nodeType === 1 && (node.classList?.contains('assistant') || node.classList?.contains('user') || node.querySelector?.('.assistant,.user'))
      ));
      if (added && sendButton && !sendButton.disabled && state.mood !== 'thinking') setMood('happy', phrase('happy'), 3200);
    });
    observer.observe(messages, { childList: true, subtree: true });
  }
  function resetIdle() {
    clearTimeout(state.idleTimer);
    state.idleTimer = setTimeout(() => setMood('sleepy', phrase('sleepy'), 5200), 180000);
  }
  ['pointerdown', 'keydown', 'touchstart'].forEach(name => window.addEventListener(name, resetIdle, { passive: true }));
  setCharacter(state.character);
  resetIdle();
})();