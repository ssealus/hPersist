// lib/command-palette.jsx — Ctrl+K modal launcher. Owned by app.jsx (state lives there).

function CommandPalette({ open, close, go }) {
  const [q, setQ] = React.useState("");
  React.useEffect(() => { if (open) setTimeout(() => document.getElementById("cmdk-input")?.focus(), 30); }, [open]);
  if (!open) return null;
  const all = [
    { id: "addinv",       label: t("nav.add_inventory") },
    { id: "inventories",  label: t("nav.inventories") },
    { id: "servers",      label: t("nav.all_servers") },
    { id: "tool.scan",    label: t("tools.network_scanner") },
    { id: "tool.redfish", label: t("tools.redfish_tester") },
    { id: "stats",        label: t("nav.stats") },
    { id: "settings",     label: t("nav.settings") },
  ];
  const filtered = all.filter(x => x.label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" style={{width: 560}} onClick={e => e.stopPropagation()}>
        <div className="hd" style={{gap: 8}}>
          <Icon.Search />
          <input id="cmdk-input" className="input" value={q} onChange={e => setQ(e.target.value)}
                 placeholder={t("app.search_placeholder")}
                 style={{border:0, background:"transparent", height: 24, padding: 0, fontSize: 14}} />
          <span className="kbd">ESC</span>
        </div>
        <div className="bd" style={{padding: 0}}>
          {filtered.map(it => (
            <div key={it.id} className="sb-item" style={{margin:"0 8px", padding: "8px 12px"}}
                 onClick={() => { go(it.id); close(); }}>
              <Icon.Right />
              <span>{it.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
