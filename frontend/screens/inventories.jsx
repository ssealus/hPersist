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
    if (!confirm(t("inventories_list.delete_confirm").replace("{name}", inv.name))) return;
    try { await api.deleteInventory(inv.id); toast.push(t("inventories_list.deleted_toast"), "ok"); reload(); }
    catch (e) { toast.push(e.message, "err"); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("nav.inventories")}</h1>
        <div className="row" style={{gap:8}}>
          <input className="input" placeholder={t("inventories_list.filter_placeholder")} value={filter} onChange={e => setFilter(e.target.value)} style={{width: 260}} />
          <button className="btn primary" onClick={() => go("addinv")}><Icon.Plus /> {t("common.new")}</button>
        </div>
      </header>

      {loading ? <Spinner /> : error ? <div className="err-panel">{error}</div> :
        rows.length === 0 ? (
          <div className="card empty">
            <p>{filter ? t("inventories_list.no_match") : t("inventories_list.no_inventories")}</p>
            {!filter && <button className="btn primary" onClick={() => go("addinv")}><Icon.Plus /> {t("nav.add_inventory")}</button>}
          </div>
        ) : (
          <table className="table">
            <thead><tr>
              <th>{t("inventories_list.col_name")}</th><th>{t("inventories_list.col_org")}</th><th>{t("inventories_list.col_mode")}</th><th>{t("inventories_list.col_servers")}</th><th>{t("inventories_list.col_status")}</th><th>{t("inventories_list.col_integrity")}</th><th>{t("inventories_list.col_duration")}</th><th>{t("inventories_list.col_created")}</th><th></th>
            </tr></thead>
            <tbody>
              {rows.map(i => (
                <tr key={i.id}>
                  <td onClick={() => go("inventories.detail", { id: i.id, name: i.name })} style={{cursor:"pointer"}}><b>{i.name}</b><div className="t-muted t-small">{i.description}</div></td>
                  <td className="t-muted">{i.organization || "—"}</td>
                  <td><span className="pill outline">{i.mode}{i.submode ? " · " + i.submode : ""}</span></td>
                  <td className="t-num">{i.reached}/{i.servers}{i.failed ? <span className="t-err"> · {i.failed} {t("inventories_list.failed_suffix")}</span> : null}</td>
                  <td><StatusPill status={i.status} /></td>
                  <td>{i.integrity_status === "ok" ? <span className="pill ok"><span className="dot"/>{t("inventories_list.integrity_verified")}</span> : i.integrity_status === "script-modified" ? <span className="pill warn"><span className="dot"/>{t("inventories_list.integrity_script_modified")}</span> : <span className="t-muted">—</span>}</td>
                  <td className="t-num t-muted">{i.duration_seconds ? i.duration_seconds.toFixed(1) + "s" : "—"}</td>
                  <td className="t-muted t-mono">{(i.created_at || "").replace("T", " ")}</td>
                  <td><button className="btn ghost sm" onClick={() => doDelete(i)} title={t("common.delete")}><Icon.Trash /></button></td>
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
  const [serversHealthFilter, setServersHealthFilter] = React.useState(null);
  const [partsLookupOpen, setPartsLookupOpen] = React.useState(false);
  const [{ loading, data, error }, reload] = usePoll(() => api.inventory(id), [id]);
  const [{ data: servers }] = usePoll(() => api.inventoryServers(id), [id]);
  const [{ data: parts }] = usePoll(() => api.inventoryParts(id), [id]);
  const [{ data: logs }] = usePoll(() => api.inventoryLogs(id), [id]);

  // ─ hooks MUST run before any early-return; placing them after `if (loading)
  //   return` triggers React's "rendered more hooks than during the previous
  //   render" check and blanks the screen ─
  const healthBuckets = React.useMemo(() => {
    const b = { ok: 0, warn: 0, err: 0, unknown: 0 };
    for (const s of servers || []) {
      const h = (s.health || "").toLowerCase();
      if (h === "ok" || h === "good") b.ok++;
      else if (h === "warning" || h === "warn") b.warn++;
      else if (h === "critical" || h === "err" || h === "fail") b.err++;
      else b.unknown++;
    }
    return b;
  }, [servers]);

  // HPE Spare PNs look like `865408-B21`, `P52562-B21`, `190885-001`,
  // `R2E09A` — short alphanumeric. DIMM vendor PNs (Hynix `HMA82GR7DJR8N-XN`,
  // Samsung `M321R4GA3EB0-CWMXJ`) are NOT in PartSurfer's index, so showing
  // them in a "look up in PartSurfer" widget is misleading.
  function looksLikeHpePn(pn) {
    if (!pn) return false;
    // Optional letter prefix + 4-7 digits + dash + 2-4 alphanumeric (most HPE SKUs).
    if (/^[A-Z]?\d{4,7}-[A-Z0-9]{2,4}$/.test(pn)) return true;
    // Short uppercase model code (e.g. R2E09A).
    if (/^[A-Z]\d[A-Z]\d{2}[A-Z]$/.test(pn)) return true;
    return false;
  }

  const topParts = React.useMemo(() =>
    (parts || []).filter(p => looksLikeHpePn(p.part_number)).slice(0, 6),
    [parts],
  );

  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;
  const inv = data;

  function jumpToServersByHealth(bucket) {
    setServersHealthFilter(bucket);
    setTab("servers");
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{inv.name}</h1>
          <div className="t-muted">{inv.organization || "—"} · {inv.description || t("inventory_detail.no_description")}</div>
        </div>
        <div className="row" style={{gap:8, flexWrap:"wrap"}}>
          <StatusPill status={inv.status} />
          <button className="btn ghost sm" onClick={() => go("tool.insight", { inventory_ids: [inv.id], autorun: true })}
                  title={t("inventory_detail.ai_summary_tooltip")}>
            <Icon.Sparkles /> {t("inventory_detail.ai_summary")}
          </button>
          <div style={{position:"relative"}}>
            <button className="btn ghost sm" onClick={() => setPartsLookupOpen(o => !o)}>
              <Icon.Cube /> {t("inventory_detail.spare_parts")}
            </button>
            {partsLookupOpen && (
              <div className="parts-popover" onMouseLeave={() => setPartsLookupOpen(false)}>
                <div className="parts-popover-hint t-muted t-small">{t("inventory_detail.top_parts_hint")}</div>
                {topParts.length === 0 ? (
                  <div className="parts-popover-empty">{t("inventory_detail.top_parts_no_hpe")}</div>
                ) : topParts.map(p => (
                  <a key={p.part_number} className="parts-popover-item"
                     title={p.label}
                     onClick={() => { setPartsLookupOpen(false); go("tool.partsurfer", { q: p.part_number }); }}>
                    <span className="pn">{p.part_number}</span>
                    <span className="desc">{p.label}</span>
                    <span className="qty">×{p.quantity}</span>
                  </a>
                ))}
              </div>
            )}
          </div>
          <button className="btn ghost sm" onClick={() => go("export.builder", { inventory_ids: [inv.id] })}><Icon.Download /> {t("inventory_detail.export")}</button>
          <button className="btn ghost sm" onClick={reload}><Icon.Refresh /> {t("common.refresh")}</button>
        </div>
      </header>

      <section className="kpi-row">
        <Kpi label={t("inventory_detail.kpi_servers")} value={inv.totals.servers} />
        <Kpi label={t("inventory_detail.kpi_components")} value={inv.totals.component_count} />
        <Kpi label={t("inventory_detail.kpi_cpu_cores")} value={inv.totals.cpu_cores} />
        <Kpi label={t("inventory_detail.kpi_memory_gb")} value={inv.totals.memory_gb} />
        <Kpi label={t("inventory_detail.kpi_storage_gb")} value={inv.totals.storage_gb} />
        <Kpi label={t("inventory_detail.kpi_psu_w")} value={inv.totals.psu_rated_watts} />
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
        <>
          <section className="grid grid-2">
            <div className="card">
              <div className="card-head">
                <h3>{t("inventory_detail.card_health")}</h3>
                <span className="t-muted t-small">{t("inventory_detail.click_to_filter")}</span>
              </div>
              <Donut segments={[
                { value: inv.health.ok,      color: "var(--accent)" },
                { value: inv.health.warn,    color: "var(--warn)" },
                { value: inv.health.err,     color: "var(--err)" },
                { value: inv.health.unknown, color: "var(--ink-3)" },
              ]} />
              <div className="health-bars">
                {[
                  { key: "ok",      label: t("inventory_detail.health_ok"),      value: inv.health.ok,      color: "var(--accent)" },
                  { key: "warn",    label: t("inventory_detail.health_warn"),    value: inv.health.warn,    color: "var(--warn)" },
                  { key: "err",     label: t("inventory_detail.health_err"),     value: inv.health.err,     color: "var(--err)" },
                  { key: "unknown", label: t("inventory_detail.health_unknown"), value: inv.health.unknown, color: "var(--ink-3)" },
                ].map(b => (
                  <button key={b.key} className="health-bar-row"
                          onClick={() => b.value > 0 && jumpToServersByHealth(b.key)}
                          disabled={b.value === 0}>
                    <span className="health-bar-label">{b.label}</span>
                    <span className="health-bar-track"><span className="health-bar-fill"
                      style={{width: `${inv.totals.servers ? (b.value / inv.totals.servers) * 100 : 0}%`, background: b.color}} /></span>
                    <span className="t-num t-muted">{b.value}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-head"><h3>{t("inventory_detail.card_models")}</h3></div>
              <HBar items={Object.entries(inv.model_distribution).slice(0,8).map(([k, v]) => ({ label: k, value: v }))} />
            </div>
          </section>

          <section className="grid grid-2">
            <div className="card">
              <div className="card-head"><h3>{t("inventory_detail.card_ilo_firmware")}</h3></div>
              <HBar items={Object.entries(inv.ilo_firmware_distribution || {}).slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
            </div>
            <div className="card">
              <div className="card-head"><h3>{t("inventory_detail.card_generation")}</h3></div>
              <HBar items={Object.entries(inv.generation_distribution || {}).slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
            </div>
          </section>

          <section className="grid grid-2">
            <div className="card">
              <div className="card-head"><h3>{t("inventory_detail.card_bios")}</h3></div>
              <HBar items={Object.entries(inv.bios_distribution || {}).slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
            </div>
            <div className="card">
              <div className="card-head">
                <h3>{t("inventory_detail.card_top_parts")}</h3>
                <span className="t-muted t-small">{t("inventory_detail.top_parts_click_hint")}</span>
              </div>
              {topParts.length === 0 ? (
                <Empty msg={t("inventory_detail.top_parts_no_hpe")} />
              ) : (
                <table className="table compact">
                  <tbody>
                    {topParts.map(p => (
                      <tr key={p.part_number} className="row-clickable"
                          onClick={() => go("tool.partsurfer", { q: p.part_number })}>
                        <td className="t-mono">{p.part_number}</td>
                        <td className="t-muted" style={{whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:280}}>{p.label}</td>
                        <td className="t-num">×{p.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </>
      )}

      {tab === "servers" && (
        <>
          <div className="row" style={{gap:6, marginBottom:8, flexWrap:"wrap"}}>
            {[
              { key: null,      label: t("inventory_detail.filter_all"),     count: servers?.length || 0 },
              { key: "ok",      label: t("inventory_detail.health_ok"),      count: healthBuckets.ok },
              { key: "warn",    label: t("inventory_detail.health_warn"),    count: healthBuckets.warn },
              { key: "err",     label: t("inventory_detail.health_err"),     count: healthBuckets.err },
              { key: "unknown", label: t("inventory_detail.health_unknown"), count: healthBuckets.unknown },
            ].map(chip => (
              <button key={chip.key || "all"}
                      className={"chip" + (serversHealthFilter === chip.key ? " active" : "")}
                      onClick={() => setServersHealthFilter(chip.key)}>
                {chip.label} <span className="t-num t-muted">{chip.count}</span>
              </button>
            ))}
          </div>
          <table className="table">
            <thead><tr>
              <th>{t("inventory_detail.col_hostname")}</th><th>{t("inventory_detail.col_ilo_ip")}</th><th>{t("inventory_detail.col_model")}</th><th>{t("inventory_detail.col_ilo")}</th><th>{t("inventory_detail.col_bios")}</th><th>{t("inventory_detail.col_cores_gb_tb")}</th><th>{t("inventory_detail.col_status_health")}</th><th>{t("inventory_detail.col_status")}</th>
            </tr></thead>
            <tbody>
              {(servers || []).filter(s => {
                if (serversHealthFilter === null) return true;
                const h = (s.health || "").toLowerCase();
                if (serversHealthFilter === "ok") return h === "ok" || h === "good";
                if (serversHealthFilter === "warn") return h === "warning" || h === "warn";
                if (serversHealthFilter === "err") return h === "critical" || h === "err" || h === "fail";
                if (serversHealthFilter === "unknown") return !s.health;
                return true;
              }).map(s => (
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
        </>
      )}

      {tab === "parts" && (
        <table className="table">
          <thead><tr><th>{t("inventory_detail.col_group")}</th><th>{t("inventory_detail.col_component")}</th><th>{t("inventory_detail.col_hpe_pn")}</th><th>{t("inventory_detail.col_qty")}</th><th>{t("inventory_detail.col_servers")}</th><th>{t("inventory_detail.col_manufacturer")}</th></tr></thead>
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
            <h3>{t("inventory_detail.card_collection_log")}</h3>
            <a className="btn ghost sm" href={`/api/v1/inventories/${id}/logs?format=txt`} target="_blank" rel="noreferrer"><Icon.Download /> {t("inventory_detail.download_log")}</a>
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
          <div className="card-head"><h3>{t("inventory_detail.card_integrity")}</h3></div>
          <dl className="kv">
            <dt>{t("inventory_detail.integrity_mode")}</dt><dd>{inv.mode} · {inv.submode}</dd>
            <dt>{t("inventory_detail.integrity_collector_version")}</dt><dd className="t-mono">{inv.collector_version || "—"}</dd>
            <dt>{t("inventory_detail.integrity_status_label")}</dt><dd>{inv.integrity_status === "ok" ? <span className="pill ok"><span className="dot"/>{t("inventories_list.integrity_verified")}</span> : inv.integrity_status === "script-modified" ? <span className="pill warn"><span className="dot"/>{t("inventory_detail.integrity_script_modified_info")}</span> : <span className="t-muted">—</span>}</dd>
            <dt>{t("inventory_detail.integrity_notes")}</dt><dd className="t-muted">{inv.integrity_notes || "—"}</dd>
            <dt>{t("inventory_detail.integrity_created_by")}</dt><dd>{inv.created_by || "—"}</dd>
            <dt>{t("inventory_detail.integrity_duration")}</dt><dd className="t-num">{inv.duration_seconds ? inv.duration_seconds.toFixed(1) + "s" : "—"}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
