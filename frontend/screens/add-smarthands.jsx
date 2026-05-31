// screens/add-smarthands.jsx — generate a portable archive + ingest the returned envelope.

function SmartHandsGen({ go }) {
  const [meta, setMeta] = React.useState({ name: "", organization: "", description: "" });
  const [csvText, setCsvText] = React.useState("");
  const [result, setResult] = React.useState(null);
  const toast = useToast();

  async function generate() {
    if (!meta.name) { toast.push(t("smart_hands.toast_name_required"), "err"); return; }
    try {
      const r = await api.smartHandsGenerate({ ...meta, csv_text: csvText || null });
      setResult(r);
      toast.push(t("smart_hands.toast_archive_generated"), "ok");
    } catch (e) { toast.push(e.message, "err"); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("smart_hands.generate_title")}</h1>
        <p className="t-muted">{t("smart_hands.generate_subtitle")}</p>
      </header>

      <section className="card">
        <div className="card-head"><h3>{t("smart_hands.section_inventory_details")}</h3></div>
        <div className="grid grid-2">
          <Field label={t("smart_hands.field_name")}><input className="input" value={meta.name} onChange={e => setMeta({...meta, name: e.target.value})} /></Field>
          <Field label={t("smart_hands.field_organization")}><input className="input" value={meta.organization} onChange={e => setMeta({...meta, organization: e.target.value})} /></Field>
          <Field label={t("smart_hands.field_description")} style={{gridColumn:"1 / -1"}}><input className="input" value={meta.description} onChange={e => setMeta({...meta, description: e.target.value})} /></Field>
        </div>

        <Field label={t("smart_hands.field_csv_prefill")} hint={t("smart_hands.field_csv_prefill_hint")} style={{marginTop:12}}>
          <textarea className="textarea t-mono" rows={6} value={csvText} placeholder="ip,hostname,login,password" onChange={e => setCsvText(e.target.value)} />
        </Field>

        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>{t("common.cancel")}</button>
          <button className="btn primary" onClick={generate}><Icon.Download /> {t("smart_hands.generate_btn")}</button>
        </div>
      </section>

      {result && (
        <section className="card">
          <div className="card-head"><h3>{t("smart_hands.section_archive_ready")}</h3></div>
          <dl className="kv">
            <dt>{t("smart_hands.label_filename")}</dt><dd className="t-mono">{result.archive}</dd>
            <dt>{t("smart_hands.label_size")}</dt><dd className="t-num">{(result.size_bytes/1024).toFixed(1)} KB</dd>
            <dt>{t("smart_hands.label_sha256")}</dt><dd className="t-mono">{result.sha256}</dd>
            <dt>{t("smart_hands.label_inventory_id")}</dt><dd className="t-mono">{result.inventory_id}</dd>
          </dl>
          <div className="row" style={{gap:8, marginTop:12}}>
            <a className="btn primary" href={result.download_url}><Icon.Download /> {t("smart_hands.download_btn")}</a>
            <button className="btn ghost" onClick={() => go("inventories.detail", { id: result.inventory_id, name: meta.name })}>{t("smart_hands.view_pending")} <Icon.Right /></button>
          </div>
          <p className="t-muted" style={{marginTop:12}}>{t("smart_hands.send_instructions")}</p>
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
      if (r.accepted) toast.push(t("smart_hands.toast_results_accepted"), "ok");
      else toast.push(t("smart_hands.toast_verification_failed"), "err");
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("smart_hands.process_title")}</h1>
        <p className="t-muted">{t("smart_hands.process_subtitle")}</p>
      </header>

      <section className="card">
        <div className="card-head"><h3>{t("smart_hands.section_upload")}</h3></div>
        <div className="dropzone">
          <input type="file" id="hpr-file" accept=".hpr,.tar.gz,.json" onChange={e => setFile(e.target.files?.[0] || null)} />
          <label htmlFor="hpr-file">
            <Icon.Download />
            {file ? <><b>{file.name}</b> <span className="t-muted">({(file.size/1024).toFixed(1)} KB)</span></>
                  : <span className="t-muted">{t("smart_hands.dropzone_prompt")}</span>}
          </label>
        </div>
        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn ghost" onClick={() => go("addinv")}>{t("common.cancel")}</button>
          <button className="btn primary" onClick={process} disabled={!file || busy}>{busy ? <Spinner /> : <Icon.Check />} {t("smart_hands.process_btn")}</button>
        </div>
      </section>

      {report && (
        <section className="card">
          <div className="card-head">
            <h3>{t("smart_hands.section_verification")}</h3>
            {report.accepted ? <span className="pill ok"><span className="dot"/>{t("smart_hands.status_accepted")}</span> : <span className="pill err"><span className="dot"/>{t("smart_hands.status_rejected")}</span>}
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
              <button className="btn primary" onClick={() => go("inventories.detail", { id: report.inventory_id })}>{t("smart_hands.view_inventory")} <Icon.Right /></button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
