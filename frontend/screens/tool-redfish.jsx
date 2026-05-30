// screens/tool-redfish.jsx — ad-hoc Redfish probe + persistent history (click to restore).

function ToolRedfish() {
  const [endpoints, setEndpoints] = React.useState([]);
  const [history, setHistory] = React.useState([]);
  const [host, setHost] = React.useState("");
  const [user, setUser] = React.useState("Administrator");
  const [pass, setPass] = React.useState("");
  const [method, setMethod] = React.useState("GET");
  const [path, setPath] = React.useState("/redfish/v1/");
  const [tls, setTls] = React.useState("warn-only");
  const [body, setBody] = React.useState("");
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const toast = useToast();

  React.useEffect(() => { api.redfishEndpoints().then(setEndpoints); api.redfishHistory().then(setHistory); }, []);

  async function send() {
    if (!host) { toast.push("host required", "err"); return; }
    setBusy(true);
    try {
      let parsedBody = null;
      if (body.trim()) try { parsedBody = JSON.parse(body); } catch { toast.push("invalid JSON body", "err"); setBusy(false); return; }
      const r = await api.redfishTest({ host, username: user, password: pass, method, path, tls, body: parsedBody, timeout: 8 });
      setResult(r);
      api.redfishHistory().then(setHistory);
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  function restoreFromHistory(h) {
    // password is never persisted — user re-enters it before re-sending
    setHost(h.host || "");
    setUser(h.username || "");
    setPass("");
    setMethod(h.method || "GET");
    setPath(h.path || "/redfish/v1/");
    setTls(h.tls || "warn-only");
    setBody(h.request_body ? JSON.stringify(h.request_body, null, 2) : "");
    toast.push("Restored — re-enter password to send", "ok");
  }

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">Redfish tester</h1></header>

      <section className="grid" style={{gridTemplateColumns: "1fr 1fr", gap: 16}}>
        <div className="card">
          <div className="card-head"><h3>Request</h3></div>
          <Field label="iLO host or IP *"><input className="input t-mono" placeholder="10.0.0.10" value={host} onChange={e => setHost(e.target.value)} /></Field>
          <div className="grid grid-2">
            <Field label="Username"><input className="input t-mono" value={user} onChange={e => setUser(e.target.value)} /></Field>
            <Field label="Password"><input className="input t-mono" type="password" value={pass} onChange={e => setPass(e.target.value)} /></Field>
          </div>
          <div className="grid grid-2">
            <Field label="Method">
              <select className="input" value={method} onChange={e => setMethod(e.target.value)}>
                <option>GET</option><option>POST</option><option>PATCH</option><option>DELETE</option>
              </select>
            </Field>
            <Field label="TLS">
              <select className="input" value={tls} onChange={e => setTls(e.target.value)}>
                <option value="strict">strict</option><option value="warn-only">warn-only</option><option value="off">off</option>
              </select>
            </Field>
          </div>
          <Field label="Path">
            <input className="input t-mono" value={path} onChange={e => setPath(e.target.value)} list="rf-endpoints" />
            <datalist id="rf-endpoints">{endpoints.map(p => <option key={p} value={p} />)}</datalist>
          </Field>
          {method !== "GET" && (
            <Field label="JSON body"><textarea className="textarea t-mono" rows={5} value={body} onChange={e => setBody(e.target.value)} /></Field>
          )}
          <button className="btn primary" onClick={send} disabled={busy} style={{marginTop:8}}>{busy ? <Spinner /> : <Icon.Plus />} Send</button>

          <div style={{marginTop: 16}}>
            <div className="t-muted t-small">Common endpoints</div>
            <div className="row" style={{flexWrap: "wrap", gap: 4, marginTop: 6}}>
              {endpoints.slice(0, 12).map(p => (
                <button key={p} className="chip" onClick={() => setPath(p)}>{p}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3>Response</h3>{result && <span className={"pill " + (result.ok ? "ok" : "err")}><span className="dot"/>{result.status} · {result.ms}ms</span>}</div>
          {result ? (
            <>
              {result.error ? <div className="err-panel">{result.error}</div> : null}
              <pre className="codeblock">{JSON.stringify(result.body || result.headers, null, 2)}</pre>
            </>
          ) : <Empty msg="No request sent yet." />}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>History</h3>
          <span className="t-muted t-small">click a row to restore — password is never stored</span>
        </div>
        <table className="table compact">
          <thead><tr><th>Host</th><th>Method</th><th>Path</th><th>User</th><th>Status</th><th>RTT</th></tr></thead>
          <tbody>
            {history.map((h, i) => (
              <tr key={i} className="row-clickable" onClick={() => restoreFromHistory(h)} title="Click to restore into the form">
                <td className="t-mono">{h.host || "—"}{h.port && h.port !== 443 ? ":" + h.port : ""}</td>
                <td className="t-mono">{h.method}</td>
                <td className="t-mono">{h.path}</td>
                <td className="t-mono t-muted">{h.username || "—"}</td>
                <td><span className={"pill " + (h.status >= 200 && h.status < 300 ? "ok" : h.status === 0 ? "err" : "warn")}>{h.status}</span></td>
                <td className="t-num t-muted">{h.ms}ms</td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr><td colSpan="6" className="t-muted" style={{textAlign:"center", padding:"16px"}}>No requests sent yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
