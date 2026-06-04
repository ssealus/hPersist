// network-bg.js — drifting graph of "servers" around a central hPersist node.
// Pure Canvas, no deps. Honours `prefers-reduced-motion`. Pauses when tab is hidden.
(function () {
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // Mount canvas once; surviving across Material's instant-nav swaps is enough,
  // we just re-resize on viewport changes.
  if (document.querySelector(".hpersist-bg")) return;

  const canvas = document.createElement("canvas");
  canvas.className = "hpersist-bg";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  const ctx = canvas.getContext("2d");

  const ACCENT = "#00ff88";
  const N_SATELLITES = 28;          // more nodes → fuller, more massive feel
  const CONNECT_DIST = 360;         // px — link satellites that are this close
  const DRIFT = 0.05;               // base velocity magnitude — slow drift
  const NODE_R = 2.2;
  const PULSE_SPEED = 0.004;        // ~5× slower than v1, calm breathing
  const HALO_R = 110;               // central node halo radius (px @1×)

  let w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
  let nodes = [];

  function resize() {
    w = canvas.width = window.innerWidth * dpr;
    h = canvas.height = window.innerHeight * dpr;
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
  }

  function seed() {
    nodes = [];
    // Span ~80% of the viewport — large and airy, not a tight cluster.
    const spread = Math.min(w, h) * 0.45;
    for (let i = 0; i < N_SATELLITES; i++) {
      const ang = (i / N_SATELLITES) * Math.PI * 2 + Math.random() * 0.3;
      const r = spread * (0.45 + Math.random() * 0.55);
      nodes.push({
        x: w / 2 + Math.cos(ang) * r,
        y: h / 2 + Math.sin(ang) * r,
        vx: (Math.random() - 0.5) * DRIFT * dpr,
        vy: (Math.random() - 0.5) * DRIFT * dpr,
        pulse: Math.random() * Math.PI * 2,
      });
    }
  }

  resize();
  seed();
  window.addEventListener("resize", () => { resize(); seed(); });

  let running = true;
  document.addEventListener("visibilitychange", () => { running = !document.hidden; if (running) requestAnimationFrame(tick); });

  function tick(t) {
    if (!running) return;
    ctx.clearRect(0, 0, w, h);

    // Connections — satellite ↔ satellite (only when close) at low alpha.
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
        const d = Math.hypot(dx, dy);
        const maxD = CONNECT_DIST * dpr;
        if (d < maxD) {
          const a = (1 - d / maxD) * 0.18;
          ctx.strokeStyle = `rgba(0, 255, 136, ${a})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
        }
      }
    }

    // Connections — central ↔ satellite (a stronger feel, all satellites).
    const cx = w / 2, cy = h / 2;
    for (const n of nodes) {
      const dx = n.x - cx, dy = n.y - cy;
      const d = Math.hypot(dx, dy);
      const a = Math.max(0, 0.22 - d / (600 * dpr));
      if (a > 0.02) {
        ctx.strokeStyle = `rgba(0, 255, 136, ${a})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(n.x, n.y);
        ctx.stroke();
      }
    }

    // Satellites — pulsing dots with free drift, no spring-pull.
    // (the spring caused the "rapid expand/contract" feel; pure drift is calmer)
    for (const n of nodes) {
      n.pulse += PULSE_SPEED;
      const r = (NODE_R + Math.sin(n.pulse) * 0.5) * dpr;
      ctx.fillStyle = "rgba(0, 255, 136, 0.55)";
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fill();

      n.x += n.vx;
      n.y += n.vy;
      // Soft wrap — nodes that fall off one edge reappear on the opposite one
      // rather than bouncing, which keeps motion uniformly slow.
      if (n.x < -40) n.x = w + 40;
      else if (n.x > w + 40) n.x = -40;
      if (n.y < -40) n.y = h + 40;
      else if (n.y > h + 40) n.y = -40;
    }

    // Central hPersist node — bigger halo for the "massive" feel.
    const halo = ctx.createRadialGradient(cx, cy, 2, cx, cy, HALO_R * dpr);
    halo.addColorStop(0, "rgba(0, 255, 136, 0.45)");
    halo.addColorStop(0.6, "rgba(0, 255, 136, 0.06)");
    halo.addColorStop(1, "rgba(0, 255, 136, 0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, HALO_R * dpr, 0, Math.PI * 2);
    ctx.fill();

    // Solid centre dot — matches satellite brightness so it doesn't pop out
    // of the gradient as a "laser point". The halo carries the focus.
    ctx.fillStyle = "rgba(0, 255, 136, 0.45)";
    ctx.beginPath();
    ctx.arc(cx, cy, 3 * dpr, 0, Math.PI * 2);
    ctx.fill();

    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();
