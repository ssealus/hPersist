// lib/widgets.jsx — small reusables shared across screens.

const Spinner = () => <span className="spinner" />;
const Empty = ({ msg }) => <div className="empty">{msg}</div>;

function Field({ label, hint, children, style }) {
  return (
    <label className="field" style={style}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint t-muted">{hint}</span>}
    </label>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value t-num">{value}</div>
    </div>
  );
}

function usePoll(fn, deps, intervalMs) {
  const [state, setState] = React.useState({ loading: true, data: null, error: null });
  const tick = React.useCallback(async () => {
    try {
      const d = await fn();
      setState({ loading: false, data: d, error: null });
    } catch (e) {
      setState({ loading: false, data: null, error: e.message || String(e) });
    }
  }, deps || []);
  React.useEffect(() => {
    tick();
    if (!intervalMs) return;
    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [tick, intervalMs]);
  return [state, tick];
}

function Sparkline({ points, h = 28 }) {
  const max = Math.max(...points), min = Math.min(...points);
  const w = 100, range = max - min || 1;
  const path = points.map((p, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((p - min) / range) * h;
    return (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1);
  }).join(" ");
  const area = path + ` L ${w} ${h} L 0 ${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height: h }}>
      <path className="spark-fill" d={area} />
      <path className="spark-line" d={path} />
    </svg>
  );
}

// DailyBars — vertical bar chart for daily-counts series. Replaces Sparkline
// for "runs per day" data where lines connecting zeros look misleading.
function DailyBars({ points, h = 64, color = "var(--accent)" }) {
  const max = Math.max(1, ...points);
  return (
    <div className="daily-bars" style={{ height: h }}>
      {points.map((v, i) => (
        <div key={i} className="daily-bar-wrap" title={`day -${points.length - 1 - i}: ${v}`}>
          <div className="daily-bar"
               style={{
                 height: v > 0 ? `${(v / max) * 100}%` : "2px",
                 background: v > 0 ? color : "var(--line)",
                 opacity: v > 0 ? 1 : 0.6,
               }} />
        </div>
      ))}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    "complete":          { cls: "ok",      label: t("status.complete") },
    "complete-warn":     { cls: "warn",    label: t("status.complete_warn") },
    "in-progress":       { cls: "info",    label: t("status.in_progress") },
    "awaiting-results":  { cls: "outline", label: t("status.awaiting_results") },
    "failed":            { cls: "err",     label: t("status.failed") },
    "ok":                { cls: "ok",      label: t("status.healthy") },
    "warn":              { cls: "warn",    label: t("status.warning") },
    "err":               { cls: "err",     label: t("status.critical") },
  };
  const s = map[status] || { cls: "outline", label: status };
  return <span className={"pill " + s.cls}><span className="dot" />{s.label}</span>;
}
