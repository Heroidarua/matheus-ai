(() => {
  'use strict';
  if (window.__adaPestinhaInitialized) return;
  window.__adaPestinhaInitialized = true;

  const storageKey = 'ada-pestinha-v2';
  const themes = {
    bryan: { name: 'Bryan', frame: '#c8d2ce', shell: '#111416', screen: '#191e20', eye: '#d8fff0', shine: '#ffffff', tie: false },
    jorge: { name: 'Jorge', frame: '#c8c2b5', shell: '#141414', screen: '#1d1d1d', eye: '#f5e5bf', shine: '#ffffff', tie: true }
  };
  const memes = {
    bryan: {
      happy: ['feliz/feliz_3.webp','feliz/feliz_5.webp','feliz/feliz_7.webp','feliz/feliz_9.webp'],
      thinking: ['trabalhando/trabalho_20.webp','trabalhando/trabalho_22.webp','trabalhando/trabalho_24.webp'],
      angry: ['bravo/bravo_11.webp','bravo/bravo_13.webp','bravo/bravo_16.webp'],
      sad: ['triste/triste_29.webp','triste/triste_31.webp','triste/triste_34.webp']
    },
    jorge: {
      happy: ['feliz/jorge_feliz_01.webp','feliz/jorge_feliz_03.webp','feliz/jorge_feliz_05.webp'],
      curious: ['curioso/jorge_curioso_01.webp','curioso/jorge_curioso_03.webp','curioso/jorge_curioso_05.webp'],
      angry: ['bravo/jorge_bravo_01.webp','bravo/jorge_bravo_03.webp','bravo/jorge_bravo_05.webp'],
      calm: ['contente/jorge_contente_01.webp','contente/jorge_contente_03.webp','contente/jorge_contente_05.webp']
    }
  };
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}') || {}; } catch {}
  let petId = saved.pet === 'jorge' ? 'jorge' : 'bryan';
  let affection = Math.max(0, Number(saved.affection) || 0);
  let mood = 'idle';
  let moodTimer = 0;
  let idleTimer = 0;

  const style = document.createElement('style');
  style.textContent = `
    #ada-pestinha{position:fixed;z-index:45;left:calc(100vw - 200px);top:calc(100vh - 260px);right:auto;bottom:auto;width:178px;display:flex;flex-direction:column;align-items:flex-end;gap:8px;font-family:Inter,ui-sans-serif,system-ui,sans-serif;pointer-events:none;background:transparent!important;transition:left 1.8s cubic-bezier(.2,.75,.25,1),top 1.8s cubic-bezier(.2,.75,.25,1);will-change:left,top}
    #ada-pestinha *{box-sizing:border-box}
    #ada-pestinha .pet-bubble{display:flex;flex-direction:column;gap:7px;max-width:178px;padding:10px 11px;border:1px solid var(--border,#343434);border-radius:13px 13px 3px 13px;background:var(--panel,#151515);color:var(--text,#eee);box-shadow:0 8px 28px #0008;font-size:11px;line-height:1.4;opacity:0;transform:translateY(7px) scale(.97);transition:opacity .2s ease,transform .2s ease;pointer-events:none}
    #ada-pestinha.show .pet-bubble{opacity:1;transform:translateY(0) scale(1)}
    #ada-pestinha .pet-bubble img{display:none;width:100%;max-height:116px;object-fit:contain;border-radius:8px;background:#080808}
    #ada-pestinha .pet-bubble.has-meme img{display:block}
    #ada-pestinha .pet-row{display:flex;align-items:flex-end;gap:6px;pointer-events:auto}
    #ada-pestinha .pet-stage{position:relative;width:154px;height:122px;display:grid;place-items:center;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;background:transparent!important;filter:drop-shadow(0 7px 7px #0005);outline:none}
    #ada-pestinha .pet-stage:focus-visible{outline:2px solid var(--accent,#63e56f);outline-offset:3px;border-radius:18px}
    #ada-pestinha .pet-svg{width:154px;height:122px;overflow:visible;background:transparent!important}\n    #ada-pestinha.dragging .pet-stage{cursor:grabbing}\n    #ada-pestinha[data-walking="true"] .pet-body{animation:adaPetWalk .28s ease-in-out infinite alternate}\n    @keyframes adaPetWalk{from{transform:translateY(1px) rotate(-3deg)}to{transform:translateY(-3px) rotate(3deg)}}
    #ada-pestinha .pet-body{transform-origin:50% 85%;animation:adaPetBob 3.2s ease-in-out infinite}
    #ada-pestinha .pet-shadow{transform-origin:center;animation:adaPetShadow 3.2s ease-in-out infinite}
    #ada-pestinha .pet-eyes{transform-origin:center;animation:adaPetBlink 5.1s infinite}
    #ada-pestinha .eye-left,#ada-pestinha .eye-right{transition:transform .2s ease}
    #ada-pestinha[data-mood="happy"] .pet-body{animation:adaPetHop .62s ease-in-out 2}
    #ada-pestinha[data-mood="happy"] .eye-left,#ada-pestinha[data-mood="happy"] .eye-right{transform:scaleY(.55)}
    #ada-pestinha[data-mood="thinking"] .eye-left{transform:translateY(-3px) scaleY(.9)}
    #ada-pestinha[data-mood="thinking"] .eye-right{transform:translateY(-3px) scaleY(.9)}
    #ada-pestinha[data-mood="curious"] .eye-right{transform:scaleY(1.28) rotate(-8deg)}
    #ada-pestinha[data-mood="sad"] .eye-left,#ada-pestinha[data-mood="sad"] .eye-right{transform:translateY(5px) scaleY(.75)}
    #ada-pestinha[data-mood="angry"] .eye-left,#ada-pestinha[data-mood="angry"] .eye-right{transform:scaleY(.75) rotate(-10deg)}
    #ada-pestinha[data-mood="sleepy"] .pet-eyes{transform:scaleY(.12);animation:none}
    #ada-pestinha .jorge-tie{display:none}
    #ada-pestinha[data-pet="jorge"] .jorge-tie{display:block}
    #ada-pestinha .pet-menu{display:none;position:absolute;right:0;bottom:100%;margin-bottom:5px;min-width:150px;padding:6px;border:1px solid var(--border,#343434);border-radius:12px;background:var(--panel,#151515);box-shadow:0 10px 30px #0009;pointer-events:auto}
    #ada-pestinha.menu-open .pet-menu{display:grid;gap:4px}
    #ada-pestinha .pet-menu button{border:0;border-radius:8px;padding:8px 9px;background:transparent;color:var(--text,#eee);font:inherit;font-size:11px;text-align:left;cursor:pointer}
    #ada-pestinha .pet-menu button:hover{background:var(--panel2,#252525)}
    #ada-pestinha .pet-caption{font-size:9px;color:var(--muted,#999);text-align:right;padding-right:8px;letter-spacing:.04em}
    #ada-pestinha .pet-hide{width:22px;height:22px;border:1px solid var(--border,#444);border-radius:50%;background:var(--panel,#151515);color:var(--muted,#aaa);font-size:14px;cursor:pointer;pointer-events:auto}
    @keyframes adaPetBob{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-5px) rotate(1.5deg)}}
    @keyframes adaPetShadow{0%,100%{transform:scaleX(1);opacity:.23}50%{transform:scaleX(.84);opacity:.12}}
    @keyframes adaPetBlink{0%,43%,47%,100%{transform:scaleY(1)}45%{transform:scaleY(.1)}}
    @keyframes adaPetHop{0%,100%{transform:translateY(0) rotate(0)}35%{transform:translateY(-15px) rotate(-6deg)}68%{transform:translateY(-5px) rotate(5deg)}}
    @media(max-width:600px){#ada-pestinha{transform:scale(.82);transform-origin:top left}}
    @media(prefers-reduced-motion:reduce){#ada-pestinha *,#ada-pestinha *:before{animation:none!important;transition:none!important}}
  `;
  document.head.appendChild(style);

  const root = document.createElement('aside');
  root.id = 'ada-pestinha';
  root.dataset.pet = petId;
  root.dataset.mood = mood;
  root.setAttribute('aria-label','Pestinha, companheiro virtual da ADA-M');
  root.innerHTML = `
    <div class="pet-bubble" role="status" aria-live="polite"><span class="pet-message">Oi! Sou o Bryan. Vamos ficar juntos por aqui? 🐾</span><img alt="Reação do Pestinha"></div>
    <div class="pet-row">
      <button class="pet-hide" type="button" aria-label="Ocultar Pestinha" title="Ocultar">×</button>
      <div style="position:relative">
        <div class="pet-menu" role="menu">
          <button type="button" data-action="bryan">🐸 Bryan — original</button>
          <button type="button" data-action="jorge">🕶️ Jorge — personagem</button>
          <button type="button" data-action="hide">Ocultar bichinho</button>
        </div>
        <button class="pet-stage" type="button" aria-label="Fazer carinho no Pestinha" title="Clique para fazer carinho; botão direito para opções">
          <svg class="pet-svg" viewBox="0 0 160 130" aria-hidden="true">
            <ellipse class="pet-shadow" cx="80" cy="117" rx="37" ry="6" fill="#000"/>
            <g class="pet-body">
              <path d="M44 106 Q39 114 30 111 M116 106 Q121 114 130 111" fill="none" stroke="var(--pet-frame)" stroke-width="7" stroke-linecap="round"/>
              <rect x="20" y="18" width="120" height="90" rx="19" fill="var(--pet-shell)" stroke="var(--pet-frame)" stroke-width="5"/>
              <rect x="29" y="27" width="102" height="72" rx="12" fill="var(--pet-screen)" stroke="var(--pet-frame)" stroke-opacity=".55" stroke-width="1.5"/>
              <g class="pet-eyes" fill="var(--pet-eye)">
                <rect class="eye-left" x="48" y="48" width="17" height="29" rx="8"/>
                <rect class="eye-right" x="95" y="48" width="17" height="29" rx="8"/>
                <circle cx="53" cy="54" r="3.2" fill="var(--pet-shine)"/>
                <circle cx="100" cy="54" r="3.2" fill="var(--pet-shine)"/>
              </g>
              <path class="jorge-tie" d="M74 91 L86 91 L84 97 L89 106 L80 111 L71 106 L76 97Z" fill="#b3261e" stroke="#65120f" stroke-width="1"/>
              <path d="M26 35 Q30 30 37 30" fill="none" stroke="#fff" stroke-opacity=".16" stroke-width="2" stroke-linecap="round"/>
            </g>
            <g class="pet-spark" fill="var(--pet-frame)"><path d="M143 25 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3Z"/></g>
          </svg>
        </button>
        <div class="pet-caption">PESTINHA · ADA-M</div>
      </div>
    </div>
  `;
  document.body.appendChild(root);

  const message = root.querySelector('.pet-message');
  const memeImage = root.querySelector('.pet-bubble img');
  const stage = root.querySelector('.pet-stage');
  const menu = root.querySelector('.pet-menu');
  const closeButton = root.querySelector('.pet-hide');
  const prompt = document.getElementById('prompt');
  const sendButton = document.getElementById('send');
  const form = document.querySelector('form');
  const messages = document.getElementById('messages');

  let neuralTypingTimer = 0;\n  let roamTimer = 0;\n  let dragState = null;\n  let suppressPetClick = false;
  const neuralMoods = {
    feliz: 'happy', contente: 'happy', observando: 'idle',
    curioso: 'curious', bravo: 'angry', triste: 'sad',
    assustado: 'curious', dramatico: 'angry', dormindo: 'sleepy'
  };
  const neuralLines = {
    feliz: 'A rede neural ficou animada com você! 💚',
    contente: 'Estou tranquilo por aqui. 😊',
    observando: 'Estou observando o que acontece…',
    curioso: 'Isso despertou minha curiosidade! 👀',
    bravo: 'Ei! Não gostei muito disso…',
    triste: 'Fiquei um pouquinho quieto agora.',
    assustado: 'Opa! Que susto! 😳',
    dramatico: 'Isso foi dramático demais!',
    dormindo: 'Estou ficando com sono…'
  };
  async function notifyNeural(event) {
    try {
      const response = await fetch('/api/pestinha/stimulus', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pet: petId, event})
      });
      if (!response.ok) return;
      const state = await response.json();
      const next = neuralMoods[state.emotion] || 'idle';
      root.dataset.neuralEmotion = state.emotion;
      // O estado neural atualiza a personalidade visual, mas não substitui
      // uma fala autônoma do Gemma por mensagens genéricas como "observando".
      root.dataset.neuralEvent = event;
    } catch {}
  }


  let autonomousRequestPending = false;
  async function askGemmaForPestinhaReaction() {
    if (autonomousRequestPending || document.visibilityState === 'hidden' || !messages) return;
    const userBubbles = [...messages.querySelectorAll('.bubble.user')];
    const assistantBubbles = [...messages.querySelectorAll('.bubble.assistant')];
    const latestUser = userBubbles[userBubbles.length - 1];
    const latestAssistant = assistantBubbles[assistantBubbles.length - 1];
    if (!latestUser || !latestAssistant || latestAssistant.classList.contains('error')) return;
    const userText = (latestUser.innerText || latestUser.textContent || '').trim().slice(0, 1200);
    const assistantText = (latestAssistant.innerText || latestAssistant.textContent || '').trim().slice(0, 1800);
    if (!userText || !assistantText) return;
    autonomousRequestPending = true;
    try {
      const response = await fetch('/api/pestinha/think', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pet: petId, user_text: userText, assistant_text: assistantText})
      });
      if (!response.ok) return;
      const decision = await response.json();
      if (decision.speak && typeof decision.text === 'string' && decision.text.trim()) {
        const allowedMoods = ['curious', 'happy', 'thinking', 'idle', 'sleepy'];
        const nextMood = allowedMoods.includes(decision.mood) ? decision.mood : 'curious';
        showMood(nextMood, decision.text.trim().slice(0, 160), 6500, false);
      }
    } catch {
      // A camada autônoma é opcional: falhas nunca afetam o chat principal.
    } finally {
      autonomousRequestPending = false;
    }
  }

  function chatBounds() {
    const rect = messages?.getBoundingClientRect();
    const top = rect ? Math.max(72, rect.top + 8) : 72;
    const bottom = rect ? Math.min(window.innerHeight - 170, rect.bottom - 210) : window.innerHeight - 190;
    const left = rect ? Math.max(8, rect.left + 4) : 8;
    const right = rect ? Math.min(window.innerWidth - 188, rect.right - 178) : window.innerWidth - 188;
    return {left, right: Math.max(left, right), top, bottom: Math.max(top, bottom)};
  }
  function movePet(x, y, walking = true) {
    const bounds = chatBounds();
    const nextX = Math.max(bounds.left, Math.min(bounds.right, x));
    const nextY = Math.max(bounds.top, Math.min(bounds.bottom, y));
    root.style.left = nextX + 'px';
    root.style.top = nextY + 'px';
    root.dataset.walking = walking ? 'true' : 'false';
    if (walking) {
      clearTimeout(root._walkStopTimer);
      root._walkStopTimer = setTimeout(() => { root.dataset.walking = 'false'; }, 1900);
    }
  }
  function scheduleWander() {
    clearTimeout(roamTimer);
    roamTimer = setTimeout(() => {
      if (!dragState && !document.hidden && root.isConnected && !root.classList.contains('menu-open')) {
        const bounds = chatBounds();
        const currentX = parseFloat(root.style.left) || bounds.right;
        const currentY = parseFloat(root.style.top) || bounds.bottom;
        const targetX = bounds.left + Math.random() * Math.max(0, bounds.right - bounds.left);
        const targetY = bounds.top + Math.random() * Math.max(0, bounds.bottom - bounds.top);
        if (Math.hypot(targetX - currentX, targetY - currentY) > 95) movePet(targetX, targetY, true);
      }
      scheduleWander();
    }, 6500 + Math.random() * 6500);
  }
  function beginPetDrag(event) {
    if (event.button !== undefined && event.button !== 0) return;
    const rect = root.getBoundingClientRect();
    dragState = {pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: rect.left, originY: rect.top, moved: false};
    try { stage.setPointerCapture(event.pointerId); } catch {}
  }
  function movePetDrag(event) {
    if (!dragState || event.pointerId !== dragState.pointerId) return;
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    if (Math.abs(dx) + Math.abs(dy) > 7) {
      dragState.moved = true;
      root.classList.add('dragging');
      movePet(dragState.originX + dx, dragState.originY + dy, false);
    }
  }
  function endPetDrag(event) {
    if (!dragState || (event.pointerId !== undefined && event.pointerId !== dragState.pointerId)) return;
    suppressPetClick = dragState.moved;
    dragState = null;
    root.classList.remove('dragging');
    root.dataset.walking = 'false';
    if (suppressPetClick) setTimeout(() => { suppressPetClick = false; }, 80);
  }
  stage.addEventListener('pointerdown', beginPetDrag);
  stage.addEventListener('pointermove', movePetDrag);
  stage.addEventListener('pointerup', endPetDrag);
  stage.addEventListener('pointercancel', endPetDrag);
  window.addEventListener('resize', () => {
    const bounds = chatBounds();
    movePet(parseFloat(root.style.left) || bounds.right, parseFloat(root.style.top) || bounds.bottom, false);
  });
  window.addEventListener('scroll', () => {
    const bounds = chatBounds();
    movePet(parseFloat(root.style.left) || bounds.right, parseFloat(root.style.top) || bounds.bottom, false);
  }, {passive:true});
  function save(){try{localStorage.setItem(storageKey,JSON.stringify({pet:petId,affection}));}catch{}}
  function theme(){
    const t=themes[petId];
    root.dataset.pet=petId;
    root.style.setProperty('--pet-frame',t.frame);
    root.style.setProperty('--pet-shell',t.shell);
    root.style.setProperty('--pet-screen',t.screen);
    root.style.setProperty('--pet-eye',t.eye);
    root.style.setProperty('--pet-shine',t.shine);
    message.textContent=petId==='jorge'?'Sou o Jorge. Tenho uma proposta… brincadeira! 😎':'Sou o Bryan. Vamos brincar um pouco? 🐾';
    memeImage.removeAttribute('src');
    root.querySelector('.pet-bubble').classList.remove('has-meme');
  }
  function showMood(next,text,duration=3200,withMeme=false){
    mood=next;
    root.dataset.mood=next;
    if(text) message.textContent=text;
    if(withMeme){
      const choices=memes[petId][next]||memes[petId].happy;
      const path=choices[Math.floor(Math.random()*choices.length)];
      memeImage.src='/static/pestinha/pets/'+petId+'/memes/'+path;
      root.querySelector('.pet-bubble').classList.add('has-meme');
    } else {
      memeImage.removeAttribute('src');
      root.querySelector('.pet-bubble').classList.remove('has-meme');
    }
    root.classList.add('show');
    clearTimeout(moodTimer);
    if(duration>0) moodTimer=setTimeout(()=>{mood='idle';root.dataset.mood='idle';root.classList.remove('show');},duration);
  }
  function setPet(id){
    petId=id==='jorge'?'jorge':'bryan';save();theme();
    showMood('happy',petId==='jorge'?'Jorge chegou! Agora é comigo. 😎':'Bryan voltou! Senti sua falta. 💚',3500,true);
    notifyNeural('activity');
    root.classList.remove('menu-open');
  }
  function toggleMenu(){root.classList.toggle('menu-open');}
  stage.addEventListener('click',()=>{
    affection=Math.min(9999,affection+1);save();
    const lines=petId==='jorge'?['Um carinho? Excelente investimento! 😎','Gostei. Pode repetir.','Sua atenção é meu ativo favorito.']:['Hehe! Carinho recebido! 💚','Mais um carinho, por favor!','Pulei de felicidade!'];
    showMood('happy',lines[Math.floor(Math.random()*lines.length)],3500);
    notifyNeural('pet');
  });
  stage.addEventListener('contextmenu',event=>{event.preventDefault();toggleMenu();});
  menu.addEventListener('click',event=>{
    const action=event.target.closest('button')?.dataset.action;
    if(action==='bryan'||action==='jorge')setPet(action);
    if(action==='hide')root.remove();
  });
  closeButton.addEventListener('click',()=>{root.remove();});
  document.addEventListener('pointerdown',event=>{if(!root.contains(event.target))root.classList.remove('menu-open');},{passive:true});

  if(prompt) prompt.addEventListener('input',()=>{
    if(prompt.value.trim()&&mood!=='thinking')showMood('curious',petId==='jorge'?'Está preparando uma ideia genial?':'O que estamos aprontando?',1800);
    clearTimeout(neuralTypingTimer);
    if(prompt.value.trim()) neuralTypingTimer=setTimeout(()=>notifyNeural('typing'),900);
  });
  if(form) form.addEventListener('submit',()=>{
    if(prompt&&prompt.value.trim())showMood('thinking','A ADA-M está pensando… vou acompanhar de perto. 🤔',0);
    notifyNeural('submit');
  },true);
  if(sendButton){
    let wasSending = Boolean(sendButton.disabled);
    const observer=new MutationObserver(()=>{
      const isSending = Boolean(sendButton.disabled);
      if(isSending) showMood('thinking','Processando… estou trabalhando junto!',0);
      else if(mood==='thinking') showMood('happy','Resposta pronta! Olha só! ✨',4500,Math.random()<.45);
      if(wasSending && !isSending) setTimeout(askGemmaForPestinhaReaction, 350);
      wasSending = isSending;
    });
    observer.observe(sendButton,{attributes:true,attributeFilter:['disabled']});
  }
  if(messages){
    const observer=new MutationObserver(records=>{
      const added=records.some(record=>[...record.addedNodes].some(node=>node.nodeType===1&&(node.classList?.contains('assistant')||node.classList?.contains('user')||node.querySelector?.('.assistant,.user'))));
      if(added&&sendButton&&!sendButton.disabled) {
        notifyNeural('response');
        setTimeout(askGemmaForPestinhaReaction, 1200);
      }
    });
    observer.observe(messages,{childList:true,subtree:true});
  }
  theme();
  idleTimer=setTimeout(()=>showMood('sleepy','Zzz… vou descansar um pouquinho.',5000),240000);
  ['pointerdown','keydown','touchstart'].forEach(name=>window.addEventListener(name,()=>{
    clearTimeout(idleTimer);
    idleTimer=setTimeout(()=>showMood('sleepy','Zzz… pode me chamar quando quiser.',5000),240000);
  },{passive:true}));
})();
