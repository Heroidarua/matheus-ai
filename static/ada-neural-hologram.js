(() => {
  const overlay = document.getElementById('live-experience');
  const visual = overlay?.querySelector('.live-visual');
  if (!overlay || !visual || visual.dataset.neuralHologram === 'ready') return;
  visual.dataset.neuralHologram = 'ready';

  // O holograma substitui a forma de onda rígida por um campo neural contínuo.
  visual.replaceChildren();
  const canvas = document.createElement('canvas');
  canvas.className = 'neural-hologram-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  visual.appendChild(canvas);

  const style = document.createElement('style');
  style.textContent = `
    .live-visual {
      position: relative !important;
      width: min(94vw, 760px) !important;
      height: clamp(300px, 54vh, 560px) !important;
      min-height: 300px !important;
      display: grid !important;
      place-items: center !important;
      overflow: visible !important;
      isolation: isolate;
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
    }
    .neural-hologram-canvas {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
      filter: saturate(1.16);
      opacity: .98;
      touch-action: none;
    }
    @media (max-width: 520px) {
      .live-visual { width: 100vw !important; height: min(56vh, 440px) !important; min-height: 270px !important; }
    }
    @media (prefers-reduced-motion: reduce) {
      .neural-hologram-canvas { opacity: .82; }
    }
  `;
  document.head.appendChild(style);

  const ctx = canvas.getContext('2d', { alpha: true, desynchronized: true });
  if (!ctx) return;
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let width = 1, height = 1, dpr = 1, frame = 0, lastTime = 0;
  let particles = [];
  let pointer = { x: 0, y: 0, active: false };
  const mobile = () => window.matchMedia('(max-width: 520px)').matches;
  const rand = (min, max) => min + Math.random() * (max - min);

  function makeParticle(index, total) {
    // Distribuição volumétrica irregular: não forma uma esfera ou anel perfeito.
    const theta = rand(0, Math.PI * 2);
    const z = rand(-1, 1);
    const radial = Math.sqrt(1 - z * z) * Math.sqrt(Math.random());
    return {
      x: Math.cos(theta) * radial,
      y: z * rand(.76, 1.08),
      z: Math.sin(theta) * radial,
      vx: rand(-.0015, .0015),
      vy: rand(-.0015, .0015),
      vz: rand(-.0012, .0012),
      phase: rand(0, Math.PI * 2),
      size: rand(.55, 1.75),
      pulse: rand(.6, 1.5),
      hue: rand(0, 1),
      index
    };
  }

  function resize() {
    const rect = visual.getBoundingClientRect();
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    dpr = Math.min(window.devicePixelRatio || 1, 1.65);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const target = mobile() ? 138 : 238;
    particles = Array.from({ length: target }, (_, i) => makeParticle(i, target));
  }

  const observer = new ResizeObserver(resize);
  observer.observe(visual);
  resize();

  function draw(now) {
    if (overlay.hidden || document.hidden) {
      frame = requestAnimationFrame(draw);
      return;
    }
    const dt = Math.min(2.2, Math.max(.35, (now - (lastTime || now)) / 16.67));
    lastTime = now;
    const t = now * .00016;
    const audio = Number.parseFloat(getComputedStyle(visual).getPropertyValue('--voice-level')) || 0;
    const state = overlay.dataset.state || 'listening';
    const speech = state === 'speaking';
    const thought = state === 'thinking';
    const energy = Math.min(1, Math.max(audio * 1.7, speech ? .19 : thought ? .105 : .055));
    const cx = width * (.5 + Math.sin(t * .83) * .025);
    const cy = height * (.5 + Math.cos(t * .67) * .035);
    const radius = Math.min(width * .34, height * .39) * (1 + energy * .13);
    const projected = [];
    ctx.clearRect(0, 0, width, height);

    // Cada ponto percorre um campo de fluxo diferente; a nuvem nunca fica congelada.
    for (const p of particles) {
      const phase = t + p.phase;
      const curlX = Math.sin(p.y * 3.7 + phase) * Math.cos(p.z * 3.1 - phase * .7);
      const curlY = Math.sin(p.z * 3.4 - phase * .8) * Math.cos(p.x * 3.8 + phase);
      const curlZ = Math.sin(p.x * 3.2 + phase * .65) * Math.cos(p.y * 3.5 - phase);
      const impulse = .00048 + energy * .0019;
      p.vx += curlX * impulse * dt;
      p.vy += curlY * impulse * dt;
      p.vz += curlZ * impulse * dt;
      p.vx += -p.x * .00012 * dt;
      p.vy += -p.y * .0001 * dt;
      p.vz += -p.z * .00012 * dt;
      const damping = Math.pow(.982, dt);
      p.vx *= damping; p.vy *= damping; p.vz *= damping;
      p.x += p.vx * dt * (reduceMotion ? .45 : 1);
      p.y += p.vy * dt * (reduceMotion ? .45 : 1);
      p.z += p.vz * dt * (reduceMotion ? .45 : 1);

      const length = Math.sqrt(p.x*p.x + p.y*p.y + p.z*p.z);
      if (length > 1.22) {
        const pull = 1.12 / length;
        p.x *= pull; p.y *= pull; p.z *= pull;
        p.vx -= p.x * .0007; p.vy -= p.y * .0007; p.vz -= p.z * .0007;
      }

      const rot = t * .42 + p.phase * .018;
      const rx = p.x * Math.cos(rot) - p.z * Math.sin(rot);
      const rz = p.x * Math.sin(rot) + p.z * Math.cos(rot);
      const perspective = 1.12 / (1.55 + rz * .42);
      const x = cx + rx * radius * 1.8 * perspective;
      const y = cy + p.y * radius * 1.8 * perspective;
      const depth = (rz + 1.25) / 2.5;
      const pulse = .68 + Math.sin(now * .0012 * p.pulse + p.phase) * .22;
      const alpha = Math.min(.95, (.22 + depth * .56 + energy * .2) * pulse);
      projected.push({ x, y, depth, alpha, size: p.size * (.7 + depth * .75) * (1 + energy * .7), hue: p.hue });
    }

    // Conexões curtas e efêmeras: sinapses aparecem e desaparecem organicamente.
    const maxDistance = mobile() ? 29 : 36;
    for (let i = 0; i < projected.length; i++) {
      const a = projected[i];
      for (let j = i + 1; j < projected.length; j++) {
        const b = projected[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < maxDistance) {
          const proximity = 1 - dist / maxDistance;
          const alpha = proximity * Math.min(a.alpha, b.alpha) * (.12 + energy * .22);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = 'rgba(255,75,91,' + alpha.toFixed(3) + ')';
          ctx.lineWidth = .45 + proximity * .55;
          ctx.stroke();
        }
      }
    }

    // Núcleos luminosos com halo difuso, sem contorno geométrico ou eixo central.
    for (const p of projected) {
      const glow = p.size * (3.2 + energy * 3.5);
      const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glow);
      gradient.addColorStop(0, 'rgba(255,245,244,' + (p.alpha * .92).toFixed(3) + ')');
      gradient.addColorStop(.18, 'rgba(255,105,115,' + (p.alpha * .66).toFixed(3) + ')');
      gradient.addColorStop(.58, 'rgba(255,45,68,' + (p.alpha * .18).toFixed(3) + ')');
      gradient.addColorStop(1, 'rgba(255,25,55,0)');
      ctx.beginPath();
      ctx.fillStyle = gradient;
      ctx.arc(p.x, p.y, glow, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.fillStyle = 'rgba(255,224,225,' + Math.min(.9, p.alpha).toFixed(3) + ')';
      ctx.arc(p.x, p.y, Math.max(.55, p.size * (.62 + energy * .7)), 0, Math.PI * 2);
      ctx.fill();
    }

    // Névoa volumétrica muito sutil que pulsa com a voz, sem formar um disco fixo.
    const mist = ctx.createRadialGradient(cx, cy, radius * .04, cx, cy, radius * (1.08 + energy * .22));
    mist.addColorStop(0, 'rgba(255,40,65,' + (.025 + energy * .045) + ')');
    mist.addColorStop(.55, 'rgba(180,20,42,' + (.012 + energy * .018) + ')');
    mist.addColorStop(1, 'rgba(100,0,20,0)');
    ctx.fillStyle = mist;
    ctx.fillRect(0, 0, width, height);

    frame = requestAnimationFrame(draw);
  }

  visual.addEventListener('pointermove', event => {
    const rect = visual.getBoundingClientRect();
    pointer.x = (event.clientX - rect.left) / rect.width;
    pointer.y = (event.clientY - rect.top) / rect.height;
    pointer.active = true;
  }, { passive: true });
  visual.addEventListener('pointerleave', () => { pointer.active = false; }, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !frame) frame = requestAnimationFrame(draw);
  });
  window.addEventListener('beforeunload', () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
  }, { once: true });
  frame = requestAnimationFrame(draw);
})();