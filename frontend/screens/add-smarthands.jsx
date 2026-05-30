// screens/add-smarthands.jsx — generate a portable archive + ingest the returned envelope.

function SmartHandsGen({ go }) {
  const [meta, setMeta] = React.useState({ name: "", organization: "", description: "" });
  const [csvText, setCsvText] = React.useState("");
  const [result, setResult] = React.useState(null);
  const toast = useToast();

  async function generate() {
    if (!meta.name) { toast.push("Name is required", "err"); return; }
    try {
      const r = await api.smartHandsGenerate({ ...meta, csv_text: csvText || null });
      setResult(r);
      toast.push("Archive generated", "ok");
    } catch (e) { toast.push(e.message, "err"); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">Generate Smart Hands collector</h1>
        <p className="t-muted">Ship a portable archive. Engineer runs it, sends back <code>results.hpr</code>.</p>
      </header>

      <section className="card">
        <div className="card-head"><h3>Inventory details</h3></div>
        <div className="grid grid-2">
          <Field label="Inventory name *"><input className="input" value={meta.name} onChange={e => setMeta({...meta, name: e.target.value})} /></Field>
          <Field label="Organization"><input className="input" value={meta.organization} onChange={e => setMeta({...meta, organization: e.target.value})} /></Field>
          <Field label="Description" style={{gridColumn:"1 / -1"}}><input className="input" value={meta.description} onChange={e => setMeta({...meta, description: e.target.value})} /></Field>
        </div>

        <Field label="Pre-filled inventory CSV (optional)" hint="The remote engineer can also fill this in themselves." style={{marginTop:12}}>
          <textarea className="textarea t-mono" rows={6} value={csvText} placeholder="ip,hostname,login,password" onChange={e => setCsvText(e.target.value)} />
        </Field>

        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>Cancel</button>
          <button className="btn primary" onClick={generate}><Icon.Download /> Generate archive</button>
        </div>
      </section>

      {result && (
        <section className="card">
          <div className="card-head"><h3>Archive ready</h3></div>
          <dl className="kv">
            <dt>Filename</dt><dd className="t-mono">{result.archive}</dd>
            <dt>Size</dt><dd className="t-num">{(result.size_bytes/1024).toFixed(1)} KB</dd>
            <dt>SHA-256</dt><dd className="t-mono">{result.sha256}</dd>
            <dt>Inventory id</dt><dd className="t-mono">{result.inventory_id}</dd>
          </dl>
          <div className="row" style={{gap:8, marginTop:12}}>
            <a className="btn primary" href={result.download_url}><Icon.Download /> Download archive</a>
            <button className="btn ghost" onClick={() => go("inventories.detail", { id: result.inventory_id, name: meta.name })}>View pending inventory <Icon.Right /></button>
          </div>
          <p className="t-muted" style={{marginTop:12}}>
            Send the archive with the README to the remote engineer — it includes setup steps and only needs Python 3.10+ and HTTPS access to the iLOs.
          </p>
        </section>
      )}
    </div>
  );
}

function SmartHandsProc({ go }) {
  const [file, setFile] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [report, setReport] = React.useState(null);
  const toast = useToast();

  async function process() {
    if (!file) return;
    setBusy(true); setReport(null);
    try {
      const r = await api.smartHandsProcess(file);
      setReport(r);
      if (r.accepted) toast.push("Results accepted", "ok");
      else toast.push("Verification failed", "err");
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">Process Smart Hands result</h1>
        <p className="t-muted">Drop the returned <code>.hpr</code> file. We verify the signature chain and ingest.</p>
      </header>

      <section className="card">
        <div className="card-head"><h3>Upload</h3></div>
        <div className="dropzone">
          <input type="file" id="hpr-file" accept=".hpr,.tar.gz,.json" onChange={e => setFile(e.target.files?.[0] || null)} />
          <label htmlFor="hpr-file">
            <Icon.Download />
            {file ? <><b>{file.name}</b> <span className="t-muted">({(file.size/1024).toFixed(1)} KB)</span></>
                  : <span className="t-muted">Click or drop a <code>.hpr</code> file</span>}
          </label>
        </div>
        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>Cancel</button>
          <button className="btn primary" onClick={process} disabled={!file || busy}>{busy ? <Spinner /> : <Icon.Check />} Process file</button>
        </div>
      </section>

      {report && (
        <section className="card">
          <div className="card-head">
            <h3>Verification</h3>
            {report.accepted ? <span className="pill ok"><span className="dot"/>accepted</span> : <span className="pill err"><span className="dot"/>rejected</span>}
          </div>
          <ol className="verify-list">
            {report.steps.map((s, i) => (
              <li key={i} className={"verify-step " + s.result}>
                <span className={"vstep-mark " + s.result}>{s.result === "ok" ? "✔" : s.result === "warn" ? "⚠" : "✗"}</span>
                <div><b>{s.label}</b><div className="t-muted">{s.detail}</div></div>
              </li>
            ))}
          </ol>
          {report.accepted && (
            <div className="row" style={{marginTop:12, justifyContent:"flex-end"}}>
              <button className="btn primary" onClick={() => go("inventories.detail", { id: report.inventory_id })}>View inventory <Icon.Right /></button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
