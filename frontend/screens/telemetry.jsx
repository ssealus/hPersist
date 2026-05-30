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
        <h1 className="t-h1">Telemetry</h1>
        <a className="btn ghost sm" href={api.statsExportUrl(30)} target="_blank" rel="noreferrer"><Icon.Download /> Export anonymized JSON</a>
      </header>

      <section className="kpi-row">
        <Kpi label="Runs (30d)" value={tel.runs} />
        <Kpi label="Servers touched" value={tel.servers_touched} />
        <Kpi label="p50 host (ms)" value={tel.timing_ms.p50} />
        <Kpi label="p99 host (ms)" value={tel.timing_ms.p99} />
        <Kpi label="DB · MB" value={(s.db_bytes/1024/1024).toFixed(1)} />
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>Daily runs (last 30d)</h3></div>
          <Sparkline points={tel.daily_runs.length ? tel.daily_runs : [0]} h={60} />
        </div>
        <div className="card">
          <div className="card-head"><h3>Modes</h3></div>
          <HBar items={Object.entries(tel.modes).map(([k, v]) => ({ label: k, value: v }))} />
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card">
          <div className="card-head"><h3>iLO mix</h3></div>
          <HBar items={Object.entries(tel.ilo_mix).map(([k, v]) => ({ label: k, value: v }))} />
        </div>
        <div className="card">
          <div className="card-head"><h3>Errors</h3></div>
          {Object.keys(tel.errors).length ? (
            <HBar items={Object.entries(tel.errors).map(([k, v]) => ({ label: k, value: v, color: "var(--err)" }))} />
          ) : <Empty msg="No errors in window — nice." />}
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h3>Storage footprint</h3></div>
        <dl className="kv">
          <dt>Database</dt><dd className="t-num">{(s.db_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>Logs</dt><dd className="t-num">{(s.logs_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>Archives</dt><dd className="t-num">{(s.archives_bytes/1024/1024).toFixed(2)} MB</dd>
          <dt>Inventories · servers</dt><dd className="t-num">{s.inventories} · {s.servers}</dd>
        </dl>
        <p className="t-muted t-small" style={{marginTop:8}}>
          The anonymized export contains no SNs, IPs, hostnames or organisations — only counts, percentiles and distributions. Safe to share with maintainers for benchmarking.
        </p>
      </section>
    </div>
  );
}
