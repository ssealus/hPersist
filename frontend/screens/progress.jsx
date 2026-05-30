// screens/progress.jsx — live WS-driven collection view, route addinv.progress.

function CollectionProgress({ go, params }) {
  const id = params.id;
  const name = params.name;
  const [hosts, setHosts] = React.useState({});
  const [job, setJob] = React.useState({ state: "starting", total: 0, completed: 0, failed: 0 });

  React.useEffect(() => {
    if (!id) return;
    const ws = api.jobSocket(id, evt => {
      if (evt.type === "job.start")  setJob(j => ({ ...j, state: "running", total: evt.total }));
      if (evt.type === "job.done")   setJob(j => ({ ...j, state: "done", completed: evt.completed, failed: evt.failed, duration: evt.duration }));
      if (evt.type === "host.start") setHosts(h => ({ ...h, [evt.host]: { host: evt.host, stage: "auth", progress: 5 } }));
      if (evt.type === "host.progress") setHosts(h => ({ ...h, [evt.host]: { ...h[evt.host], stage: evt.stage, progress: evt.progress } }));
      if (evt.type === "host.done")  setHosts(h => ({ ...h, [evt.host]: { ...h[evt.host], stage: "done", progress: 100, duration: evt.duration, components: evt.components } }));
      if (evt.type === "host.failed")setHosts(h => ({ ...h, [evt.host]: { ...h[evt.host], stage: "error", progress: 100, error: evt.error } }));
    });
    return () => ws.close();
  }, [id]);

  const rows = Object.values(hosts);
  const ok = rows.filter(r => r.stage === "done").length;
  const failed = rows.filter(r => r.stage === "error").length;

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">Collecting · {name || id}</h1>
        <div className="row" style={{gap:8}}>
          <StatusPill status={job.state === "done" ? (failed ? "complete-warn" : "complete") : "in-progress"} />
          <button className="btn ghost sm" onClick={() => go("inventories.detail", { id, name })}>Open inventory <Icon.Right /></button>
        </div>
      </header>

      <section className="kpi-row">
        <Kpi label="Total" value={job.total} />
        <Kpi label="OK" value={ok} />
        <Kpi label="Failed" value={failed} />
        <Kpi label="In flight" value={rows.length - ok - failed} />
      </section>

      <section className="card">
        <div className="card-head"><h3>Hosts</h3></div>
        <table className="table compact">
          <thead><tr><th>Host</th><th>Stage</th><th>Progress</th><th>Components</th><th>Duration</th><th>Notes</th></tr></thead>
          <tbody>
            {rows.sort((a, b) => a.host.localeCompare(b.host)).map(r => (
              <tr key={r.host}>
                <td className="t-mono">{r.host}</td>
                <td><span className={"pill " + (r.stage === "done" ? "ok" : r.stage === "error" ? "err" : "info")}><span className="dot"/>{r.stage}</span></td>
                <td><div className="progress small"><div style={{width:`${r.progress || 0}%`}} /></div></td>
                <td className="t-num">{r.components ?? "—"}</td>
                <td className="t-num t-muted">{r.duration ? r.duration.toFixed(1) + "s" : "—"}</td>
                <td className="t-muted">{r.error || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
