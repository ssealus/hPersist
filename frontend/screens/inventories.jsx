// screens/inventories.jsx — list of collection runs + per-inventory detail.

function InventoriesList({ go }) {
  const [{ loading, data, error }, reload] = usePoll(() => api.inventories(), [], 8000);
  const [filter, setFilter] = React.useState("");
  const toast = useToast();

  const rows = (data || []).filter(i =>
    !filter ||
    (i.name || "").toLowerCase().includes(filter.toLowerCase()) ||
    (i.organization || "").toLowerCase().includes(filter.toLowerCase())
  );

  async function doDelete(inv) {
    if (!confirm(`Delete inventory "${inv.name}"? This cannot be undone.`)) return;
    try { await api.deleteInventory(inv.id); toast.push("Inventory deleted", "ok"); reload(); }
    catch (e) { toast.push(e.message, "err"); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("nav.inventories")}</h1>
        <div className="row" style={{gap:8}}>
          <input className="input" placeholder="Filter by name or org…" value={filter} onChange={e => setFilter(e.target.value)} style={{width: 260}} />
          <button className="btn primary" onClick={() => go("addinv")}><Icon.Plus /> New</button>
        </div>
      </header>

      {loading ? <Spinner /> : error ? <div className="err-panel">{error}</div> :
        rows.length === 0 ? (
          <div className="card empty">
            <p>{filter ? "Nothing matches your filter." : "No inventories yet."}</p>
            {!filter && <button className="btn primary" onClick={() => go("addinv")}><Icon.Plus /> Add inventory</button>}
          </div>
        ) : (
          <table className="table">
            <thead><tr>
              <th>Name</th><th>Org</th><th>Mode</th><th>Servers</th><th>Status</th><th>Integrity</th><th>Duration</th><th>Created</th><th></th>
            </tr></thead>
            <tbody>
              {rows.map(i => (
                <tr key={i.id}>
                  <td onClick={() => go("inventories.detail", { id: i.id, name: i.name })} style={{cursor:"pointer"}}><b>{i.name}</b><div className="t-muted t-small">{i.description}</div></td>
                  <td className="t-muted">{i.organization || "—"}</td>
                  <td><span className="pill outline">{i.mode}{i.submode ? " · " + i.submode : ""}</span></td>
                  <td className="t-num">{i.reached}/{i.servers}{i.failed ? <span className="t-err"> · {i.failed} failed</span> : null}</td>
                  <td><StatusPill status={i.status} /></td>
                  <td>{i.integrity_status === "ok" ? <span className="pill ok"><span className="dot"/>verified</span> : i.integrity_status === "script-modified" ? <span className="pill warn"><span className="dot"/>script modified</span> : <span className="t-muted">—</span>}</td>
                  <td className="t-num t-muted">{i.duration_seconds ? i.duration_seconds.toFixed(1) + "s" : "—"}</td>
                  <td className="t-muted t-mono">{(i.created_at || "").replace("T", " ")}</td>
                  <td><button className="btn ghost sm" onClick={() => doDelete(i)} title="Delete"><Icon.Trash /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      }
    </div>
  );
}

function InventoryDetail({ go, params }) {
  const id = params.id;
  const [tab, setTab] = React.useState("overview");
  const [{ loading, data, error }, reload] = usePoll(() => api.inventory(id), [id]);
  const [{ data: servers }] = usePoll(() => api.inventoryServers(id), [id]);
  const [{ data: parts }] = usePoll(() => api.inventoryParts(id), [id]);
  const [{ data: logs }] = usePoll(() => api.inventoryLogs(id), [id]);

  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;
  const inv = data;

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{inv.name}</h1>
          <div className="t-muted">{inv.organization || "—"} · {inv.description || "no description"}</div>
        </div>
        <div className="row" style={{gap:8}}>
          <StatusPill status={inv.status} />
          <button className="btn ghost sm" onClick={() => go("export.builder", { inventory_ids: [inv.id] })}><Icon.Download /> Export</button>
          <button className="btn ghost sm" onClick={reload}><Icon.Refresh /> Refresh</button>
        </div>
      </header>

      <section className="kpi-row">
        <Kpi label="Servers" value={inv.totals.servers} />
        <Kpi label="Components" value={inv.totals.component_count} />
        <Kpi label="CPU cores" value={inv.totals.cpu_cores} />
        <Kpi label="Memory · GB" value={inv.totals.memory_gb} />
        <Kpi label="Storage · GB" value={inv.totals.storage_gb} />
        <Kpi label="PSU · W" value={inv.totals.psu_rated_watts} />
      </section>

      <nav className="tabs">
        {[
          { id: "overview",   label: t("inventory_detail.tab_overview") },
          { id: "servers",    label: t("inventory_detail.tab_servers") },
          { id: "parts",      label: t("inventory_detail.tab_parts") },
          { id: "logs",       label: t("inventory_detail.tab_logs") },
          { id: "integrity",  label: t("inventory_detail.tab_integrity") },
        ].map(({ id: tabId, label }) => (
          <button key={tabId} className={"tab" + (tab === tabId ? " active" : "")} onClick={() => setTab(tabId)}>{label}</button>
        ))}
      </nav>

      {tab === "overview" && (
        <section className="grid grid-2">
          <div className="card">
            <div className="card-head"><h3>Health</h3></div>
            <Donut segments={[
              { value: inv.health.ok,      color: "var(--accent)" },
              { value: inv.health.warn,    color: "var(--warn)" },
              { value: inv.health.err,     color: "var(--err)" },
              { value: inv.health.unknown, color: "var(--ink-3)" },
            ]} />
            <HBar items={[
              { label: "OK", value: inv.health.ok, color: "var(--accent)" },
              { label: "Warn", value: inv.health.warn, color: "var(--warn)" },
              { label: "Err", value: inv.health.err, color: "var(--err)" },
              { label: "Unknown", value: inv.health.unknown, color: "var(--ink-3)" },
            ]} />
          </div>
          <div className="card">
            <div className="card-head"><h3>Models</h3></div>
            <HBar items={Object.entries(inv.model_distribution).slice(0,8).map(([k, v]) => ({ label: k, value: v }))} />
          </div>
        </section>
      )}

      {tab === "servers" && (
        <table className="table">
          <thead><tr>
            <th>Hostname</th><th>iLO IP</th><th>Model</th><th>iLO</th><th>BIOS</th><th>Cores·GB·TB</th><th>Health</th><th>Status</th>
          </tr></thead>
          <tbody>
            {(servers || []).map(s => (
              <tr key={s.id} onClick={() => go("server.detail", { id: s.id, name: s.hostname || s.ilo_ip })} style={{cursor:"pointer"}}>
                <td><b>{s.hostname || "—"}</b></td>
                <td className="t-mono">{s.ilo_ip || "—"}</td>
                <td>{s.model || "—"}</td>
                <td className="t-mono">{s.ilo_generation || "?"} · {s.ilo_firmware || "?"}</td>
                <td className="t-mono">{s.bios_version || "—"}</td>
                <td className="t-num">— · {s.total_memory_gb || "—"} · {s.total_storage_gb ? (s.total_storage_gb/1000).toFixed(1) : "—"}</td>
                <td><StatusPill status={s.health || "ok"} /></td>
                <td><StatusPill status={s.collection_status === "ok" ? "complete" : "failed"} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "parts" && (
        <table className="table">
          <thead><tr><th>Group</th><th>Component</th><th>HPE PN</th><th>Qty</th><th>Servers</th><th>Manufacturer</th></tr></thead>
          <tbody>
            {(parts || []).map((p, i) => (
              <tr key={i}>
                <td><span className="pill outline">{p.group}</span></td>
                <td>{p.label}</td>
                <td className="t-mono">{p.part_number || "—"}</td>
                <td className="t-num"><b>{p.quantity}</b></td>
                <td className="t-num t-muted">{p.servers_touched}</td>
                <td className="t-muted">{p.manufacturer || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "logs" && (
        <div className="card">
          <div className="card-head">
            <h3>Collection log</h3>
            <a className="btn ghost sm" href={`/api/v1/inventories/${id}/logs?format=txt`} target="_blank" rel="noreferrer"><Icon.Download /> Download .log</a>
          </div>
          <pre className="logbox">
            {(logs?.lines || []).map((l, i) => (
              <div key={i} className={"logline " + l.level}>
                <span className="t-muted">{l.ts.split("T")[1]?.slice(0,12)}</span> <span className={"pill " + (l.level === "err" ? "err" : l.level === "warn" ? "warn" : l.level === "ok" ? "ok" : "info")}>{l.level}</span> <span className="t-muted">{l.host || "—"}</span> {l.message}
              </div>
            ))}
          </pre>
        </div>
      )}

      {tab === "integrity" && (
        <div className="card">
          <div className="card-head"><h3>Integrity</h3></div>
          <dl className="kv">
            <dt>Mode</dt><dd>{inv.mode} · {inv.submode}</dd>
            <dt>Collector version</dt><dd className="t-mono">{inv.collector_version || "—"}</dd>
            <dt>Integrity status</dt><dd>{inv.integrity_status === "ok" ? <span className="pill ok"><span className="dot"/>verified</span> : inv.integrity_status === "script-modified" ? <span className="pill warn"><span className="dot"/>script modified · informational</span> : <span className="t-muted">—</span>}</dd>
            <dt>Notes</dt><dd className="t-muted">{inv.integrity_notes || "—"}</dd>
            <dt>Created by</dt><dd>{inv.created_by || "—"}</dd>
            <dt>Duration</dt><dd className="t-num">{inv.duration_seconds ? inv.duration_seconds.toFixed(1) + "s" : "—"}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
