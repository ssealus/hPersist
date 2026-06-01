// screens/add-local.jsx — direct-network collection: CIDR sweep + CSV upload.

function LocalCidr({ go }) {
  const [cidr, setCidr] = React.useState("10.0.0.0/24");
  const [user, setUser] = React.useState("Administrator");
  const [pass, setPass] = React.useState("");
  const [scanning, setScanning] = React.useState(false);
  const [hits, setHits] = React.useState([]);
  const [progress, setProgress] = React.useState({ done: 0, total: 0 });
  const [selected, setSelected] = React.useState(new Set());
  const [meta, setMeta] = React.useState({ name: "", organization: "", description: "" });
  const toast = useToast();
  const esRef = React.useRef(null);

  function startScan() {
    setScanning(true); setHits([]); setSelected(new Set()); setProgress({ done: 0, total: 0 });
    const es = api.networkScan(cidr, { concurrency: 64, timeout: 1.5, probe_redfish: true });
    esRef.current = es;
    es.addEventListener("meta", e => { const d = JSON.parse(e.data); setProgress(p => ({ ...p, total: d.total })); });
    es.addEventListener("hit",  e => {
      const h = JSON.parse(e.data);
      if (h.redfish || h.tcp_443) setHits(prev => [...prev, h].sort((a, b) => a.ip.localeCompare(b.ip)));
      setProgress(p => ({ ...p, done: p.done + 1 }));
    });
    es.addEventListener("done", () => { setScanning(false); es.close(); esRef.current = null; toast.push(t("add_local.toast_scan_complete"), "ok"); });
    es.onerror = () => { setScanning(false); es.close(); esRef.current = null; };
  }

  React.useEffect(() => () => esRef.current && esRef.current.close(), []);

  function toggle(ip) { setSelected(s => { const n = new Set(s); n.has(ip) ? n.delete(ip) : n.add(ip); return n; }); }
  function selectAllRedfish() { setSelected(new Set(hits.filter(h => h.redfish).map(h => h.ip))); }

  async function start() {
    if (!meta.name) { toast.push(t("add_local.toast_name_required"), "err"); return; }
    if (!pass) { toast.push(t("add_local.toast_password_required"), "err"); return; }
    if (selected.size === 0) { toast.push(t("add_local.toast_pick_one_host"), "err"); return; }
    try {
      const r = await api.startCollection({
        name: meta.name, organization: meta.organization, description: meta.description,
        mode: "cidr",
        default_login: user, default_password: pass,
        hosts: [...selected].map(ip => ({ ip, login: user, password: pass })),
      });
      toast.push(t("add_local.toast_collection_started"), "ok");
      go("addinv.progress", { id: r.id, name: r.name });
    } catch (e) { toast.push(e.message, "err"); }
  }

  const redfishCount = hits.filter(h => h.redfish).length;
  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("add_local.cidr_title")}</h1></header>

      <section className="card">
        <div className="card-head"><h3>{t("add_local.step_scan_range")}</h3></div>
        <div className="row" style={{gap:8, alignItems:"end"}}>
          <Field label={t("add_local.field_cidr")} style={{marginBottom: 0}}><input className="input t-mono" value={cidr} onChange={e => setCidr(e.target.value)} /></Field>
          <button className="btn primary" style={{height: 30}} onClick={startScan} disabled={scanning}>{scanning ? <Spinner /> : <Icon.Refresh />} {scanning ? t("add_local.scanning") : t("add_local.start_scan")}</button>
          {scanning && <button className="btn ghost" style={{height: 30}} onClick={() => esRef.current?.close()}><Icon.X /> {t("common.stop")}</button>}
        </div>
        <div className="field-hint t-muted" style={{marginTop:6}}>{t("add_local.field_cidr_hint")}</div>
        {progress.total > 0 && (
          <div style={{marginTop:12}}>
            <div className="progress"><div style={{width:`${(progress.done/progress.total)*100}%`}}/></div>
            <div className="t-muted t-small" style={{marginTop:4}}>{t("add_local.progress_summary").replace("{done}", progress.done).replace("{total}", progress.total).replace("{reachable}", hits.length).replace("{redfish}", redfishCount)}</div>
          </div>
        )}
      </section>

      {hits.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h3>{t("add_local.step_pick_targets")} <span className="t-muted">{t("add_local.selected_count").replace("{count}", selected.size)}</span></h3>
            <button className="btn ghost sm" onClick={selectAllRedfish}>{t("add_local.select_all_redfish")}</button>
          </div>
          <table className="table compact">
            <thead><tr><th></th><th>{t("add_local.col_ip")}</th><th>{t("add_local.col_redfish")}</th><th>{t("add_local.col_rtt")}</th><th>{t("add_local.col_server_header")}</th><th>{t("add_local.col_hpe")}</th></tr></thead>
            <tbody>
              {hits.map(h => (
                <tr key={h.ip} className={selected.has(h.ip) ? "selected" : ""}>
                  <td><input type="checkbox" checked={selected.has(h.ip)} onChange={() => toggle(h.ip)} /></td>
                  <td className="t-mono">{h.ip}</td>
                  <td>{h.redfish ? <span className="pill ok"><span className="dot"/>{t("add_local.redfish_yes")}</span> : h.tcp_443 ? <span className="pill warn">{t("add_local.redfish_tcp_only")}</span> : <span className="pill err">{t("add_local.redfish_no")}</span>}</td>
                  <td className="t-num t-muted">{h.rtt_ms ? h.rtt_ms.toFixed(0) + "ms" : "—"}</td>
                  <td className="t-mono t-muted">{h.server_header || "—"}</td>
                  <td>{h.is_hpe === true ? <span className="pill ok">{t("add_local.is_hpe_hpe")}</span> : h.is_hpe === false ? <span className="pill outline">{t("add_local.is_hpe_other")}</span> : <span className="t-muted">?</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card">
        <div className="card-head"><h3>{t("add_local.step_inventory_creds")}</h3></div>
        <div className="grid grid-2">
          <Field label={t("add_local.field_name")}><input className="input" placeholder={t("add_local.field_name_placeholder")} value={meta.name} onChange={e => setMeta({...meta, name: e.target.value})} /></Field>
          <Field label={t("add_local.field_organization")}><input className="input" placeholder={t("add_local.field_organization_placeholder")} value={meta.organization} onChange={e => setMeta({...meta, organization: e.target.value})} /></Field>
          <Field label={t("add_local.field_description")} style={{gridColumn: "1 / -1"}}><input className="input" value={meta.description} onChange={e => setMeta({...meta, description: e.target.value})} /></Field>
          <Field label={t("add_local.field_default_username")}><input className="input t-mono" value={user} onChange={e => setUser(e.target.value)} /></Field>
          <Field label={t("add_local.field_default_password")}><input className="input t-mono" type="password" value={pass} onChange={e => setPass(e.target.value)} /></Field>
        </div>
        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>{t("common.cancel")}</button>
          <button className="btn primary" onClick={start} disabled={selected.size === 0}><Icon.Plus /> {t("add_local.start_collection_count").replace("{count}", selected.size)}</button>
        </div>
      </section>
    </div>
  );
}

function LocalCsv({ go }) {
  const [text, setText] = React.useState("ip,hostname,login,password\n10.0.0.10,dl380-fra-01,Administrator,changeMe\n");
  const [meta, setMeta] = React.useState({ name: "", organization: "", description: "" });
  const [report, setReport] = React.useState(null);
  const toast = useToast();

  async function validate() {
    try { setReport(await api.validateCsv(text)); }
    catch (e) { toast.push(e.message, "err"); }
  }

  async function loadTemplate() {
    setText("ip,hostname,login,password\n10.0.10.42,db-fra-01,Administrator,YourPassword\n10.0.10.43,,Administrator,YourPassword\n");
    toast.push(t("add_local.template_loaded"), "info");
  }

  async function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setText(await f.text());
  }

  async function start() {
    if (!meta.name) { toast.push(t("add_local.toast_name_required"), "err"); return; }
    if (!report || !report.summary.ok) { toast.push(t("add_local.toast_validate_first"), "err"); return; }
    try {
      // re-parse client-side so the password never leaves the local memory
      const parsed = parseClient(text);
      const hostsWithCreds = parsed.filter(r => r.ok).map(r => ({ ip: r.ip, hostname: r.hostname, login: r.login, password: r.password }));
      const r = await api.startCollection({
        name: meta.name, organization: meta.organization, description: meta.description,
        mode: "csv", hosts: hostsWithCreds,
      });
      toast.push(t("add_local.toast_collection_started"), "ok");
      go("addinv.progress", { id: r.id, name: r.name });
    } catch (e) { toast.push(e.message, "err"); }
  }

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("add_local.csv_title")}</h1></header>

      <section className="card">
        <div className="card-head"><h3>{t("add_local.step_csv_input")}</h3>
          <div className="row" style={{gap:8}}>
            <input type="file" accept=".csv,.txt" onChange={onFile} className="input-file" />
            <button className="btn ghost sm" onClick={loadTemplate}><Icon.Doc /> {t("add_local.template")}</button>
          </div>
        </div>
        <textarea className="textarea t-mono" rows={10} value={text} onChange={e => setText(e.target.value)} />
        <div className="row" style={{marginTop:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={validate}><Icon.Check /> {t("common.validate")}</button>
        </div>
        {report && (
          <div style={{marginTop:12}}>
            <div className="row" style={{gap:8}}>
              <span className="pill ok"><span className="dot"/>{t("add_local.n_valid").replace("{count}", report.summary.ok)}</span>
              {report.summary.warn > 0 && <span className="pill warn"><span className="dot"/>{t("add_local.n_warnings").replace("{count}", report.summary.warn)}</span>}
              {report.summary.err > 0 && <span className="pill err"><span className="dot"/>{t("add_local.n_errors").replace("{count}", report.summary.err)}</span>}
              {report.summary.fatal.length > 0 && <span className="t-err">{report.summary.fatal.join(" · ")}</span>}
            </div>
            {report.rows.some(r => r.status !== "ok") && (
              <table className="table compact" style={{marginTop:12}}>
                <thead><tr><th>{t("add_local.col_line")}</th><th>{t("add_local.col_ip")}</th><th>{t("add_local.col_status")}</th><th>{t("add_local.col_message")}</th></tr></thead>
                <tbody>
                  {report.rows.filter(r => r.status !== "ok").map((r, i) => (
                    <tr key={i}>
                      <td className="t-num">{r.line}</td>
                      <td className="t-mono">{r.ip || "—"}</td>
                      <td>{r.status === "err" ? <span className="pill err">err</span> : <span className="pill warn">warn</span>}</td>
                      <td className="t-muted">{r.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("add_local.step_csv_details")}</h3></div>
        <div className="grid grid-2">
          <Field label={t("add_local.field_name")}><input className="input" value={meta.name} onChange={e => setMeta({...meta, name: e.target.value})} /></Field>
          <Field label={t("add_local.field_organization")}><input className="input" value={meta.organization} onChange={e => setMeta({...meta, organization: e.target.value})} /></Field>
          <Field label={t("add_local.field_description")} style={{gridColumn:"1 / -1"}}><input className="input" value={meta.description} onChange={e => setMeta({...meta, description: e.target.value})} /></Field>
        </div>
        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>{t("common.cancel")}</button>
          <button className="btn primary" onClick={start} disabled={!report || !report.summary.ok}><Icon.Plus /> {t("add_local.start_collection")}</button>
        </div>
      </section>
    </div>
  );
}

function parseClient(text) {
  const out = [];
  const lines = text.split(/\r?\n/);
  if (!lines.length) return out;
  const header = (lines.shift() || "").split(",").map(s => s.trim().toLowerCase());
  const idx = name => header.indexOf(name);
  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    const cols = line.split(",").map(s => s.trim());
    const ip = cols[idx("ip")] || "";
    const hostname = cols[idx("hostname")] || null;
    const login = cols[idx("login")] || "";
    const password = cols[idx("password")] || "";
    const ok = /^\d+\.\d+\.\d+\.\d+$/.test(ip) && login && password;
    out.push({ ip, hostname, login, password, ok });
  }
  return out;
}
