// screens/tool-insight.jsx — AI Insight: pick inventories + mode, send to LLM, render markdown answer.

function ToolInsight() {
  const [inventories, setInventories] = React.useState([]);
  const [selected, setSelected] = React.useState(new Set());
  const [mode, setMode] = React.useState("summary");
  const [question, setQuestion] = React.useState("");
  const [templates, setTemplates] = React.useState([]);
  const [template, setTemplate] = React.useState("procurement");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [liveReasoning, setLiveReasoning] = React.useState("");
  const [liveContent, setLiveContent] = React.useState("");
  const toast = useToast();

  React.useEffect(() => {
    api.inventories().then(rs => setInventories(rs || []));
    api.insightTemplates().then(d => setTemplates(d.templates || [])).catch(() => {});
  }, []);

  function toggle(id) {
    setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  async function run() {
    if (selected.size === 0) { toast.push(t("insight.toast_pick_inventory"), "err"); return; }
    if (mode === "analytics" && !question.trim()) { toast.push(t("insight.toast_ask_question"), "err"); return; }
    setBusy(true); setResult(null); setLiveReasoning(""); setLiveContent("");
    try {
      let reasonAcc = "";
      let contentAcc = "";
      for await (const ev of api.insightRunStream({
        inventory_ids: [...selected],
        mode,
        question: mode === "analytics" ? question : null,
        template: mode === "reports" ? template : null,
      })) {
        if (ev.event === "reasoning_delta") {
          reasonAcc += ev.data.text || "";
          setLiveReasoning(reasonAcc);
        } else if (ev.event === "content_delta") {
          contentAcc += ev.data.text || "";
          setLiveContent(contentAcc);
        } else if (ev.event === "done") {
          setResult(ev.data);
        } else if (ev.event === "error") {
          toast.push(ev.data.detail || "stream error", "err");
        }
      }
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  async function testConnection() {
    try {
      const r = await api.insightTest();
      toast.push(t("insight.toast_test_ok").replace("{model}", r.model || "?"), "ok");
    } catch (e) { toast.push(e.message, "err"); }
  }

  const totalServers = inventories
    .filter(i => selected.has(i.id))
    .reduce((sum, i) => sum + (i.servers || 0), 0);

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{t("tools.ai_insight")}</h1>
          <p className="t-muted">{t("insight.subtitle")}</p>
        </div>
        <button className="btn ghost sm" onClick={testConnection}>
          <Icon.Check /> {t("insight.test_connection")}
        </button>
      </header>

      <section className="grid" style={{gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.6fr)", gap: 16}}>
        <div className="card">
          <div className="card-head">
            <h3>{t("insight.section_inventories")}</h3>
            <span className="t-muted t-small">{t("insight.servers_total").replace("{count}", totalServers)}</span>
          </div>
          {inventories.length === 0 ? (
            <Empty msg={t("insight.no_inventories")} />
          ) : (
            <table className="table compact">
              <thead><tr><th></th><th>{t("insight.col_name")}</th><th>{t("insight.col_servers")}</th><th>{t("insight.col_status")}</th></tr></thead>
              <tbody>
                {inventories.map(inv => (
                  <tr key={inv.id} className={selected.has(inv.id) ? "selected" : ""}>
                    <td><input type="checkbox" checked={selected.has(inv.id)} onChange={() => toggle(inv.id)} /></td>
                    <td>{inv.name}</td>
                    <td className="t-num">{inv.servers || 0}</td>
                    <td><StatusPill status={inv.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <div className="card-head"><h3>{t("insight.section_query")}</h3></div>

          <div className="tabs">
            <button className={"tab" + (mode === "summary" ? " active" : "")} onClick={() => setMode("summary")}>{t("insight.mode_summary")}</button>
            <button className={"tab" + (mode === "analytics" ? " active" : "")} onClick={() => setMode("analytics")}>{t("insight.mode_analytics")}</button>
            <button className={"tab" + (mode === "reports" ? " active" : "")} onClick={() => setMode("reports")}>{t("insight.mode_reports")}</button>
          </div>

          {mode === "summary" && (
            <p className="t-muted t-small">{t("insight.summary_desc")}</p>
          )}
          {mode === "analytics" && (
            <Field label={t("insight.field_question")}>
              <textarea className="textarea" rows={5} placeholder={t("insight.field_question_placeholder")}
                value={question} onChange={e => setQuestion(e.target.value)} />
            </Field>
          )}
          {mode === "reports" && (
            <Field label={t("insight.field_template")}>
              <select className="input" value={template} onChange={e => setTemplate(e.target.value)}>
                {templates.map(tpl => <option key={tpl} value={tpl}>{t("insight.template_" + tpl)}</option>)}
              </select>
            </Field>
          )}

          <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
            <button className="btn primary" onClick={run} disabled={busy}>
              {busy ? <Spinner /> : <Icon.Plus />} {t("insight.run")}
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>{t("insight.section_answer")}</h3>
          {result && result.model && (
            <span className="t-muted t-small">
              {result.anonymized && <span className="pill ok" style={{marginRight:6}}><span className="dot"/>{t("insight.anonymized")}</span>}
              {result.level && result.level !== "full" && (
                <span className="pill outline" style={{marginRight:6}}>{t("settings_page.llm_context_level_" + result.level)}</span>
              )}
              {result.model}
              {result.usage?.total_tokens ? ` · ${result.usage.total_tokens} tok` : ""}
            </span>
          )}
        </div>
        {busy ? (
          <LiveThinking reasoning={liveReasoning} content={liveContent} />
        ) : result ? (
          <InsightAnswer result={result} />
        ) : (
          <Empty msg={t("insight.no_answer_yet")} />
        )}
      </section>
    </div>
  );
}

function LiveThinking({ reasoning, content }) {
  // Reasoning streams to a back layer (dim, auto-scroll to bottom). Foreground
  // keeps the spinner + "Thinking…" label centred. When `content` starts coming
  // through (model finished reasoning, started answering) we also show it dim
  // behind so the user sees the answer building too.
  const ghostRef = React.useRef(null);
  React.useEffect(() => {
    if (ghostRef.current) ghostRef.current.scrollTop = ghostRef.current.scrollHeight;
  }, [reasoning, content]);

  const ghostText = (reasoning || "") + (content ? "\n\n" + content : "");

  return (
    <div className="thinking-stage">
      <div className="thinking-ghost" ref={ghostRef}>
        {ghostText || " "}
      </div>
      <div className="thinking-overlay">
        <Spinner />
        <span className="thinking-overlay-label">{t("insight.thinking")}</span>
      </div>
    </div>
  );
}

function InsightAnswer({ result }) {
  const empty = !(result.answer || "").trim();
  const truncated = result.finish_reason === "length";

  if (empty) {
    // Reasoning model burned its whole token budget on internal CoT —
    // content is "" but reasoning_content has the chain-of-thought.
    return (
      <>
        <div className="err-panel" style={{
          borderColor: "color-mix(in oklab, var(--warn) 40%, var(--line))",
          background: "color-mix(in oklab, var(--warn) 8%, var(--panel))",
          color: "var(--warn)",
          fontFamily: "inherit",
        }}>
          <Icon.Alert /> <b>{t("insight.empty_answer_title")}</b>
          <div style={{marginTop:4}}>
            {truncated
              ? t("insight.empty_answer_length").replace("{reasoning}", result.usage?.reasoning_tokens || "?").replace("{total}", result.usage?.total_tokens || "?")
              : t("insight.empty_answer_generic")}
          </div>
        </div>
        {result.reasoning && (
          <details style={{marginTop:12}}>
            <summary className="t-muted t-small" style={{cursor:"pointer"}}>{t("insight.show_reasoning")}</summary>
            <div className="markdown" style={{marginTop:8, opacity:0.85}}
                 dangerouslySetInnerHTML={{__html: renderMarkdown(result.reasoning)}} />
          </details>
        )}
      </>
    );
  }

  return (
    <>
      {truncated && (
        <div className="t-warn t-small" style={{marginBottom:8}}>
          <Icon.Alert /> {t("insight.truncated_warning")}
        </div>
      )}
      <div className="markdown" dangerouslySetInnerHTML={{__html: renderMarkdown(result.answer)}} />
      {result.reasoning && (
        <details style={{marginTop:12}}>
          <summary className="t-muted t-small" style={{cursor:"pointer"}}>{t("insight.show_reasoning")}</summary>
          <div className="markdown" style={{marginTop:8, opacity:0.7}}
               dangerouslySetInnerHTML={{__html: renderMarkdown(result.reasoning)}} />
        </details>
      )}
    </>
  );
}

// Tiny markdown renderer — enough for the LLM's output: headings, bold/italic, code,
// bullet lists, and pipe-tables. Keeps the bundle bundler-free.
function renderMarkdown(src) {
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = src.split(/\r?\n/);
  let out = "";
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    if (/^```/.test(line)) {
      const lang = line.replace(/^```/, "").trim();
      let body = "";
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { body += lines[i] + "\n"; i++; }
      i++;
      out += `<pre class="codeblock"><code data-lang="${esc(lang)}">${esc(body)}</code></pre>`;
      continue;
    }

    // table (header | --- | row...)
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[ :|-]+\|?\s*$/.test(lines[i + 1])) {
      const header = line.trim().replace(/^\||\|$/g, "").split("|").map(s => s.trim());
      i += 2;
      const body = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        body.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map(s => s.trim()));
        i++;
      }
      out += "<table class=\"table compact\"><thead><tr>" +
        header.map(h => `<th>${inline(h)}</th>`).join("") + "</tr></thead><tbody>" +
        body.map(row => "<tr>" + row.map(c => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table>";
      continue;
    }

    // headings
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) { out += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; i++; continue; }

    // bullets
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      out += "<ul>" + items.map(it => `<li>${inline(it)}</li>`).join("") + "</ul>";
      continue;
    }

    // blank line
    if (!line.trim()) { i++; continue; }

    // paragraph
    out += `<p>${inline(line)}</p>`;
    i++;
  }

  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/\*([^*]+)\*/g, "<i>$1</i>");
  }

  return out;
}
