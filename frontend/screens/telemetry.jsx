// screens/telemetry.jsx — Stats tab. Pulls /stats/rollup. Export is opt-in JSON.

function Telemetry() {
  const [{ loading, data, error }] = usePoll(() => api.rollup(30), [], 30000);
  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;

  const tel = data.telemetry;
  const s = data.storage;

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("telemetry.title")}</h1>
        <a className="btn ghost sm" href={api.statsExportUrl(30)} target="_blank" rel="noreferrer"><Icon.Download /> {t("telemetry.export_anonymized")}</a>
      </header>

      <section className="kpi-row">
        <Kpi label={t("telemetry.kpi_runs_30d")} value={tel.runs} />
        <Kpi label={t("telemetry.kpi_servers_touched")} value={tel.servers_touched} />
        <Kpi label={t("telemetry.kpi_p50_host_ms")} value={tel.timing_ms.p50} />
        <Kpi label={t("telemetry.kpi_p99_host_ms")} value={tel.timing_ms.p99} />
        <Kpi label={t("telemetry.kpi_db_mb")} value={(s.db_bytes/1024/1024).toFixed(1)} />
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_daily_runs")}</h3></div>
          <Sparkline points={tel.daily_runs.length ? tel.daily_runs : [0]} h={60} />
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_modes")}</h3></div>
          <HBar items={Object.entries(tel.modes).map(([k, v]) => ({ label: k, value: v }))} />
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_ilo_mix")}</h3></div>
          <HBar items={Object.entries(tel.ilo_mix).map(([k, v]) => ({ label: k, value: v }))} />
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_errors")}</h3></div>
          {Object.keys(tel.errors).length ? (
            <HBar items={Object.entries(tel.errors).map(([k, v]) => ({ label: k, value: v, color: "var(--err)" }))} />
          ) : <Empty msg={t("telemetry.no_errors")} />}
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("telemetry.card_storage_footprint")}</h3></div>
        <dl className="kv">
          <dt>{t("telemetry.label_database")}</dt><dd className="t-num">{(s.db_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>{t("telemetry.label_logs")}</dt><dd className="t-num">{(s.logs_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>{t("telemetry.label_archives")}</dt><dd className="t-num">{(s.archives_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>{t("telemetry.label_inventories_servers")}</dt><dd className="t-num">{s.inventories} · {s.servers}</dd>
        </dl>
        <p className="t-muted t-small" style={{marginTop:8}}>{t("telemetry.privacy_note")}</p>
      </section>
    </div>
  );
}
