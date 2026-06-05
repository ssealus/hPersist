// screens/dashboard.jsx — fleet overview, top route ("/" → "dashboard").

function Dashboard({ go }) {
  const [{ loading, data, error }] = usePoll(() => api.fleet(), [], 15000);

  if (loading) return <div className="screen"><h1 className="t-h1">{t("overview.title")}</h1><Spinner /></div>;
  if (error) return <div className="screen"><h1 className="t-h1">{t("overview.title")}</h1><div className="err-panel">{error}</div></div>;

  const totals = data.totals;
  const health = data.health;
  const totalHealth = health.ok + health.warn + health.err || 1;

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("overview.title")}</h1>
        <p className="t-muted">{t("overview.subtitle")}</p>
      </header>

      <section className="kpi-row">
        <Kpi label={t("overview.servers")} value={totals.servers} />
        <Kpi label={t("overview.inventories")} value={totals.inventories} />
        <Kpi label={t("overview.components")} value={totals.components} />
        <Kpi label={t("overview.avg_collection")} value={totals.avg_collection_seconds} />
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("overview.health")}</h3><span className="t-muted">{totalHealth} {t("overview.servers")}</span></div>
          <div className="row" style={{alignItems:"center", gap:24}}>
            <Donut segments={[
              { value: health.ok,   color: "var(--accent)" },
              { value: health.warn, color: "var(--warn)" },
              { value: health.err,  color: "var(--err)" },
            ]} />
            <div style={{flex:1}}>
              <HBar items={[
                { label: t("overview.health_ok"),       value: health.ok,   color: "var(--accent)" },
                { label: t("overview.health_warning"),  value: health.warn, color: "var(--warn)" },
                { label: t("overview.health_critical"), value: health.err,  color: "var(--err)" },
              ]} />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3>{t("overview.models")}</h3></div>
          {data.model_distribution.length ? (
            <Treemap items={data.model_distribution.slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
          ) : <Empty msg="No data yet — collect an inventory to see models." />}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("overview.ilo_firmware")}</h3></div>
          {data.ilo_firmware_distribution.length ? (
            <HBar items={data.ilo_firmware_distribution.slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
          ) : <Empty msg="No iLO data yet." />}
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("overview.memory_config")}</h3></div>
          {data.memory_configurations.length ? (
            <HBar items={data.memory_configurations.slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
          ) : <Empty msg="No memory data yet." />}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>{t("overview.recent_runs")}</h3>
        </div>
        {data.recent.length ? (
          <table className="table">
            <thead><tr>
              <th>{t("overview.col_name")}</th><th>{t("overview.col_organization")}</th><th>{t("overview.col_mode")}</th><th>{t("overview.col_servers")}</th><th>{t("overview.col_status")}</th><th>{t("overview.col_when")}</th>
            </tr></thead>
            <tbody>
              {data.recent.map(i => (
                <tr key={i.id} onClick={() => go("inventories.detail", { id: i.id, name: i.name })} style={{cursor:"pointer"}}>
                  <td><b>{i.name}</b></td>
                  <td className="t-muted">{i.org || "—"}</td>
                  <td><span className="pill outline">{i.mode}{i.submode ? " · " + i.submode : ""}</span></td>
                  <td className="t-num">{i.reached}/{i.servers}</td>
                  <td><StatusPill status={i.status} /></td>
                  <td className="t-muted t-mono">{(i.created_at || "").replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">
            <p>{t("overview.empty")}</p>
            <button className="btn primary" onClick={() => go("addinv")}><Icon.Plus /> {t("nav.add_inventory")}</button>
          </div>
        )}
      </section>
    </div>
  );
}
