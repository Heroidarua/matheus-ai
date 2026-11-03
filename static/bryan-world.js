(() => {
  'use strict';
  if (window.__bryanPixelWorldLoaded) return;
  window.__bryanPixelWorldLoaded = true;

  const style = document.createElement('style');
  style.textContent = `
    #bryan-world-toggle{position:fixed;right:18px;bottom:18px;z-index:9997;border:1px solid #53635d;background:#151c1a;color:#d9f5e8;border-radius:999px;padding:10px 14px;font:600 12px system-ui;cursor:pointer;box-shadow:0 8px 28px #0006}
    #bryan-world{position:fixed;right:18px;bottom:64px;z-index:9997;width:min(390px,calc(100vw - 28px));background:#101614;border:1px solid #42534b;border-radius:16px;padding:12px;color:#e7f3ec;box-shadow:0 18px 60px #0009;display:none;font:12px system-ui}
    #bryan-world.open{display:block}#bryan-world header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    #bryan-world canvas{display:block;width:100%;image-rendering:pixelated;background:#17221e;border:1px solid #35483d;border-radius:8px}
    #bryan-world .bw-status{min-height:34px;color:#b7c9bf;padding:8px 2px;line-height:1.35}
    #bryan-world .bw-actions{display:flex;gap:6px;flex-wrap:wrap}
    #bryan-world button{border:1px solid #52665b;background:#202c26;color:#e5f5eb;border-radius:8px;padding:7px 9px;font-size:11px;cursor:pointer}
    #bryan-world button:hover{background:#314238}#bryan-world .bw-small{opacity:.65;font-size:10px}
    @media(max-width:520px){#bryan-world{right:8px;bottom:60px}#bryan-world-toggle{right:10px;bottom:10px}}
  `;
  document.head.appendChild(style);

  const toggle = document.createElement('button');
  toggle.id = 'bryan-world-toggle';
  toggle.textContent = '▦ Mundo do Bryan';
  const panel = document.createElement('section');
  panel.id = 'bryan-world';
  panel.innerHTML = `
    <header><strong>▦ O mundo do Bryan</strong><span class="bw-small" id="bw-generation">Geração 1</span></header>
    <canvas id="bw-canvas" width="400" height="220" aria-label="Mundo de pixels do Bryan"></canvas>
    <div class="bw-status" id="bw-status">Bryan está preparando o seu mundo…</div>
    <div class="bw-actions">
      <button type="button" data-action="think">Deixar ele criar</button>
      <button type="button" data-action="clone">Multiplicar</button>
      <button type="button" data-action="evolve">Evoluir</button>
      <button type="button" data-action="reset">Recomeçar</button>
    </div>`;
  document.body.append(toggle, panel);
  toggle.addEventListener('click', () => panel.classList.toggle('open'));

  const canvas = panel.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  const status = panel.querySelector('#bw-status');
  const generation = panel.querySelector('#bw-generation');
  const colors = {
    grass:'#477d52', stone:'#78858b', wood:'#a97843', flag:'#e6c84f',
    barricade:'#b06b42', toy_blaster:'#75a9d8', flower:'#e88db5',
    spark:'#f3e6a2', banner:'#d76b67', clone:'#9de0c1'
  };
  let world = null, pending = false, lastActivity = Date.now(), lastDecision = 0;

  function draw(data) {
    if (!data) return;
    world = data;
    const w = data.width || 20, h = data.height || 11, cw = canvas.width / w, ch = canvas.height / h;
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = '#1c2b25'; ctx.fillRect(0,0,canvas.width,canvas.height);
    for(let y=0;y<h;y++) for(let x=0;x<w;x++){
      ctx.fillStyle = (x+y)%2 ? '#20352a' : '#1d3027';
      ctx.fillRect(x*cw,y*ch,cw,ch);
      ctx.strokeStyle = '#31473a'; ctx.strokeRect(x*cw,y*ch,cw,ch);
    }
    for(const item of data.objects || []){
      const x=Math.max(0,Math.min(w-1,item.x)), y=Math.max(0,Math.min(h-1,item.y));
      const px=x*cw, py=y*ch;
      ctx.fillStyle=colors[item.kind] || '#d0d0d0';
      ctx.fillRect(px+3,py+3,cw-6,ch-6);
      if(item.kind==='flag'||item.kind==='banner'){
        ctx.fillStyle='#e8e8d8';ctx.fillRect(px+5,py+2,2,ch-3);
        ctx.fillStyle=colors[item.kind];ctx.fillRect(px+7,py+3,cw-9,7);
      } else if(item.kind==='clone'){
        ctx.fillStyle='#10231b';ctx.fillRect(px+6,py+5,4,4);ctx.fillRect(px+cw-10,py+5,4,4);
      } else if(item.kind==='toy_blaster'){
        ctx.fillStyle='#dce9f0';ctx.fillRect(px+cw/2,py+5,cw/2-3,4);
      }
    }
    generation.textContent='Geração '+(data.generation||1);
    status.textContent=data.message || 'Bryan está construindo…';
    status.dataset.mood=data.mood || 'curious';
  }

  async function loadWorld(){
    try{const r=await fetch('/api/pestinha/world',{credentials:'same-origin'});if(r.ok)draw(await r.json());}
    catch{status.textContent='Não consegui carregar o mundo agora.';}
  }
  async function decide(){
    if(pending || document.visibilityState==='hidden' || Date.now()-lastDecision<18000) return;
    pending=true; lastDecision=Date.now();
    try{
      const r=await fetch('/api/pestinha/world/think',{method:'POST',credentials:'same-origin'});
      const data=await r.json();
      if(data.world)draw(data.world);
    }catch{ /* o jogo não interfere no chat */ }
    finally{pending=false;}
  }
  async function manual(action){
    if(action==='reset'){
      const r=await fetch('/api/pestinha/world',{method:'DELETE',credentials:'same-origin'});
      if(r.ok) await loadWorld();
      return;
    }
    if(action==='clone'||action==='evolve'){
      // As mesmas ações são escolhidas pelo modelo; o botão apenas pede uma nova decisão.
      lastDecision=0;
    }
    await decide();
  }
  panel.querySelectorAll('button[data-action]').forEach(button=>{
    button.addEventListener('click',()=>manual(button.dataset.action));
  });
  ['pointerdown','keydown','input'].forEach(name=>document.addEventListener(name,()=>{lastActivity=Date.now();},{passive:true}));
  const messages=document.getElementById('messages');
  if(messages){
    new MutationObserver(()=>{lastActivity=Date.now(); if(!panel.dataset.started){panel.dataset.started='1';setTimeout(decide,3500);}}).observe(messages,{childList:true,subtree:true});
  }
  loadWorld();
  // Pensamento limitado ao chat aberto, com intervalo mínimo e sem tráfego quando oculto/inativo.
  setInterval(()=>{
    if(Date.now()-lastActivity<180000 && document.visibilityState!=='hidden') decide();
  },30000);
})();