// lib/command-palette.jsx — Ctrl+K modal launcher. Owned by app.jsx (state lives there).

function CommandPalette({ open, close, go }) {
  const [q, setQ] = React.useState("");
  React.useEffect(() => { if (open) setTimeout(() => document.getElementById("cmdk-input")?.focus(), 30); }, [open]);
  if (!open) return null;
  const all = [
    { id: "addinv", label: "Create new inventory", hint: "Add inventory" },
    { id: "inventories", label: "All inventories" },
    { id: "servers", label: "All servers" },
    { id: "tool.scan", label: "Run network scan" },
    { id: "tool.redfish", label: "Test Redfish endpoint" },
    { id: "stats", label: "View telemetry" },
    { id: "settings", label: "Settings" },
  ];
  const filtered = all.filter(x => x.label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" style={{width: 560}} onClick={e => e.stopPropagation()}>
        <div className="hd" style={{gap: 8}}>
          <Icon.Search />
          <input id="cmdk-input" className="input" value={q} onChange={e => setQ(e.target.value)}
                 placeholder="Type a command, server, IP, SN…"
                 style={{border:0, background:"transparent", height: 24, padding: 0, fontSize: 14}} />
          <span className="kbd">ESC</span>
        </div>
        <div className="bd" style={{padding: 0}}>
          {filtered.map(it => (
            <div key={it.id} className="sb-item" style={{margin:"0 8px", padding: "8px 12px"}}
                 onClick={() => { go(it.id); close(); }}>
              <Icon.Right />
              <span>{it.label}</span>
              {it.hint && <span className="t-dim" style={{marginLeft:"auto"}}>{it.hint}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
