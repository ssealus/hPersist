// screens/telemetry.jsx — Stats tab. Pulls /stats/rollup. Export is opt-in JSON.

function Telemetry() {
  const [{ loading, data, error }] = usePoll(() => api.rollup(30), [], 30000);
  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;

  const tel = data.telemetry;
  const s = data.storage;
  const cap = tel.fleet_capacity || { total_memory_gb: 0, total_storage_gb: 0 };
  const out = tel.host_outcomes || { succeeded: 0, failed: 0, success_rate: 0 };

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("telemetry.title")}</h1>
        <a className="btn ghost sm" href={api.statsExportUrl(30)} target="_blank" rel="noreferrer"><Icon.Download /> {t("telemetry.export_anonymized")}</a>
      </header>

      <section className="kpi-row">
        <Kpi label={t("telemetry.kpi_runs_30d")}        value={tel.runs} />
        <Kpi label={t("telemetry.kpi_servers_touched")} value={tel.servers_touched} />
        <Kpi label={t("telemetry.kpi_success_rate")}    value={`${Math.round(out.success_rate * 100)}%`} />
        <Kpi label={t("telemetry.kpi_total_ram_tb")}    value={(cap.total_memory_gb / 1024).toFixed(1)} />
        <Kpi label={t("telemetry.kpi_total_storage_tb")} value={(cap.total_storage_gb / 1024).toFixed(1)} />
        <Kpi label={t("telemetry.kpi_p50_host_ms")}     value={tel.timing_ms.p50} />
        <Kpi label={t("telemetry.kpi_p99_host_ms")}     value={tel.timing_ms.p99} />
        <Kpi label={t("telemetry.kpi_db_mb")}           value={(s.db_bytes/1024/1024).toFixed(1)} />
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head">
            <h3>{t("telemetry.card_daily_runs")}</h3>
            <span className="t-muted t-small">{t("telemetry.daily_runs_axis").replace("{days}", tel.daily_runs.length || 30)}</span>
          </div>
          <DailyBars points={tel.daily_runs.length ? tel.daily_runs : [0]} h={80} />
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
          <div className="card-head"><h3>{t("telemetry.card_generation")}</h3></div>
          {Object.keys(tel.generation_mix || {}).length ? (
            <HBar items={Object.entries(tel.generation_mix).map(([k, v]) => ({ label: k, value: v }))} />
          ) : <Empty msg={t("telemetry.no_generation_data")} />}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_top_models")}</h3></div>
          <HBar items={Object.entries(tel.model_mix || {}).slice(0, 8).map(([k, v]) => ({ label: k, value: v }))} />
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_memory_per_server")}</h3></div>
          {Object.keys(tel.memory_per_server || {}).length ? (
            <HBar items={Object.entries(tel.memory_per_server).map(([k, v]) => ({ label: k, value: v }))} />
          ) : <Empty msg={t("telemetry.no_data")} />}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_drive_media")}</h3></div>
          {Object.keys(tel.drive_media || {}).length ? (
            <HBar items={Object.entries(tel.drive_media).map(([k, v]) => ({
              label: k, value: v,
              color: k === "NVMe" ? "var(--accent)" : k === "SSD" ? "color-mix(in oklab, var(--accent) 60%, var(--warn))" : "var(--ink-3)",
            }))} />
          ) : <Empty msg={t("telemetry.no_data")} />}
        </div>
        <div className="card">
          <div className="card-head"><h3>{t("telemetry.card_outcomes")}</h3></div>
          <Donut segments={[
            { value: out.succeeded, color: "var(--accent)" },
            { value: out.failed,    color: "var(--err)" },
          ]} />
          <HBar items={[
            { label: t("telemetry.outcome_succeeded"), value: out.succeeded, color: "var(--accent)" },
            { label: t("telemetry.outcome_failed"),    value: out.failed,    color: "var(--err)" },
          ]} />
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("telemetry.card_errors")}</h3></div>
        {Object.keys(tel.errors).length ? (
          <HBar items={Object.entries(tel.errors).map(([k, v]) => ({ label: k, value: v, color: "var(--err)" }))} />
        ) : <Empty msg={t("telemetry.no_errors")} />}
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
