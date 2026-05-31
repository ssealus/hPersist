// screens/servers.jsx — flat "All servers" view + single server deep-dive.

function AllServers({ go }) {
  const [{ data: inventories, loading }] = usePoll(() => api.inventories(), []);
  const [all, setAll] = React.useState([]);

  React.useEffect(() => {
    if (!inventories) return;
    Promise.all(inventories.map(i => api.inventoryServers(i.id).then(s => s.map(x => ({...x, inv_name: i.name}))).catch(() => [])))
      .then(lists => setAll(lists.flat()));
  }, [inventories]);

  if (loading) return <div className="screen"><Spinner /></div>;

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("nav.all_servers")}</h1><span className="t-muted">{t("all_servers.total_suffix").replace("{count}", all.length)}</span></header>
      <table className="table">
        <thead><tr><th>{t("all_servers.col_hostname")}</th><th>{t("all_servers.col_ilo_ip")}</th><th>{t("all_servers.col_model")}</th><th>{t("all_servers.col_inventory")}</th><th>{t("all_servers.col_ilo")}</th><th>{t("all_servers.col_status")}</th></tr></thead>
        <tbody>
          {all.map(s => (
            <tr key={s.id} onClick={() => go("server.detail", { id: s.id, name: s.hostname || s.ilo_ip })} style={{cursor:"pointer"}}>
              <td><b>{s.hostname || "—"}</b></td>
              <td className="t-mono">{s.ilo_ip}</td>
              <td>{s.model}</td>
              <td className="t-muted">{s.inv_name}</td>
              <td className="t-mono">{s.ilo_generation} · {s.ilo_firmware}</td>
              <td><StatusPill status={s.collection_status === "ok" ? "complete" : "failed"} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ServerDetail({ go, params }) {
  const id = params.id;
  const [{ loading, data, error }] = usePoll(() => api.server(id), [id]);
  const [rawOpen, setRawOpen] = React.useState(false);
  const [raw, setRaw] = React.useState(null);
  React.useEffect(() => { if (rawOpen && !raw) api.serverRaw(id).then(setRaw); }, [rawOpen, raw, id]);

  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;
  const s = data;

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{s.hostname || s.ilo_ip}</h1>
          <div className="t-muted">{s.model} · SN {s.serial_number || "—"} · {s.ilo_generation} {s.ilo_firmware}</div>
        </div>
        <button className="btn ghost sm" onClick={() => go("inventories.detail", { id: s.inventory_id })}><Icon.Left /> {t("server_detail.back")}</button>
      </header>

      <section className="kpi-row">
        <Kpi label={t("server_detail.kpi_components")} value={s.components.length} />
        <Kpi label={t("server_detail.kpi_memory_gb")} value={s.total_memory_gb || "—"} />
        <Kpi label={t("server_detail.kpi_storage_gb")} value={s.total_storage_gb || "—"} />
        <Kpi label={t("server_detail.kpi_power_state")} value={s.power_state || "—"} />
        <Kpi label={t("server_detail.kpi_collected_s")} value={s.duration_seconds || "—"} />
      </section>

      {Object.entries(s.components_by_group).map(([group, items]) => (
        <section className="card" key={group}>
          <div className="card-head"><h3>{group} <span className="t-muted t-num">({items.length})</span></h3></div>
          <table className="table compact">
            <thead><tr><th>{t("server_detail.col_description")}</th><th>{t("server_detail.col_hpe_pn")}</th><th>{t("server_detail.col_sn")}</th><th>{t("server_detail.col_location")}</th><th>{t("server_detail.col_capacity")}</th><th>{t("server_detail.col_firmware")}</th><th>{t("server_detail.col_health")}</th></tr></thead>
            <tbody>
              {items.map(c => (
                <tr key={c.id}>
                  <td>{c.label}</td>
                  <td className="t-mono">{c.part_number || "—"}</td>
                  <td className="t-mono t-muted">{c.serial_number || "—"}</td>
                  <td className="t-muted">{c.location || "—"}</td>
                  <td className="t-num">{c.capacity_value ? `${c.capacity_value} ${c.capacity_unit || ""}` : "—"}</td>
                  <td className="t-mono">{c.firmware_version || "—"}</td>
                  <td><StatusPill status={(c.health || "ok").toLowerCase()} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      <section className="card">
        <div className="card-head">
          <h3>{t("server_detail.raw_payload")}</h3>
          <button className="btn ghost sm" onClick={() => setRawOpen(o => !o)}>{rawOpen ? t("common.hide") : t("common.show")}</button>
        </div>
        {rawOpen && (raw ? <pre className="codeblock">{JSON.stringify(raw, null, 2)}</pre> : <Spinner />)}
      </section>
    </div>
  );
}
