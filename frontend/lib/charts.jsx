// lib/charts.jsx — visualisation primitives.

function Donut({ segments, size = 110, thickness = 18 }) {
  const r = size / 2 - thickness / 2;
  const c = 2 * Math.PI * r;
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  // tiny gap between segments hides subpixel-rounding bleed at boundaries;
  // skip zero-value segments entirely so they don't claim phantom offset.
  const GAP = 0.75;
  const drawn = segments.filter(s => s.value > 0);
  let off = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--line)" strokeWidth={thickness} />
      {drawn.map((s, i) => {
        const len = (s.value / total) * c;
        const drawLen = Math.max(0, len - (drawn.length > 1 ? GAP : 0));
        const el = (
          <circle key={i} cx={size/2} cy={size/2} r={r} fill="none"
            stroke={s.color} strokeWidth={thickness}
            strokeLinecap="butt"
            strokeDasharray={`${drawLen} ${c - drawLen}`}
            strokeDashoffset={-off}
            transform={`rotate(-90 ${size/2} ${size/2})`} />
        );
        off += len;
        return el;
      })}
      <text x="50%" y="48%" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="18" fill="var(--ink)">
        {total}
      </text>
      <text x="50%" y="62%" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--ink-3)" letterSpacing=".1em">
        TOTAL
      </text>
    </svg>
  );
}

function HBar({ items, max }) {
  const m = max || Math.max(...items.map(i => i.value));
  return (
    <div className="hbar">
      {items.map((it, i) => (
        <div className="row" key={i}>
          <div className="l" title={it.label}>{it.label}</div>
          <div className="t"><i style={{ width: `${(it.value / m) * 100}%`, background: it.color || "var(--accent)" }} /></div>
          <div className="v">{it.value}</div>
        </div>
      ))}
    </div>
  );
}

function Treemap({ items, color = "var(--accent)" }) {
  const total = items.reduce((a, i) => a + i.value, 0);
  return (
    <div className="tm" style={{ height: 180 }}>
      {items.map((it, i) => {
        const w = (it.value / total) * 100;
        // tint stays in 14..42% so the background never gets so bright that
        // light ink text disappears against it (dark theme would lose contrast).
        const tint = 14 + Math.min(28, (it.value / total) * 100);
        return (
          <div key={i} className="cell"
               style={{ flex: `${w} 0 ${w}%`, minWidth: 40,
                        background: `color-mix(in oklab, ${color} ${tint}%, var(--panel))` }}>
            <b>{it.label}</b>
            <span className="v">{it.value} · {Math.round(w)}%</span>
          </div>
        );
      })}
    </div>
  );
}

function Heatmap({ rows, cols, cellFn }) {
  return (
    <div className="hm" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {Array.from({ length: rows * cols }).map((_, i) => {
        const c = cellFn(i);
        return <div key={i} className={"cell " + (c.cls || "")} title={c.title || ""} />;
      })}
    </div>
  );
}
