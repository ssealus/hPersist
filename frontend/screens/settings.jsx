// screens/settings.jsx — appearance + locale + system info.

// Public LLM endpoints — when the user points the base URL here, payload may
// leak to third parties. We surface a warning unless `llm_anonymize` is on.
const PUBLIC_LLM_HOSTS = [
  "api.openai.com", "api.anthropic.com", "api.mistral.ai", "api.together.xyz",
  "api.deepinfra.com", "api.groq.com", "api.perplexity.ai", "api.x.ai",
  "openrouter.ai", "generativelanguage.googleapis.com", "api.cohere.com",
  "api.fireworks.ai", "api.deepseek.com",
];

function detectPublicProvider(url) {
  if (!url) return null;
  try {
    const u = new URL(url.includes("://") ? url : "https://" + url);
    const host = u.hostname.toLowerCase();
    return PUBLIC_LLM_HOSTS.find(h => host === h || host.endsWith("." + h)) || null;
  } catch { return null; }
}

function Settings({ locale, setLocale, theme, setTheme, density, setDensity, direction, setDirection }) {
  const [{ data: health }] = usePoll(() => api.get("/health"), []);
  const [{ data: locales }] = usePoll(() => api.locales(), []);
  const [llm, setLlm] = React.useState({ llm_base_url: "", llm_api_key: "", llm_model: "", llm_anonymize: "false", llm_context_level: "full" });
  const [llmDirty, setLlmDirty] = React.useState(false);
  const [llmBusy, setLlmBusy] = React.useState(false);
  const toast = useToast();

  React.useEffect(() => {
    api.getSettings().then(s => {
      setLlm({
        llm_base_url: s?.llm_base_url || "",
        llm_api_key: s?.llm_api_key || "",
        llm_model: s?.llm_model || "",
        llm_anonymize: s?.llm_anonymize || "false",
        llm_context_level: s?.llm_context_level || "full",
      });
    }).catch(() => {});
  }, []);

  function setLlmField(k, v) { setLlm(prev => ({...prev, [k]: v})); setLlmDirty(true); }

  const isPublicProvider = detectPublicProvider(llm.llm_base_url);
  const anonymizeOn = llm.llm_anonymize === "true";

  async function saveLlm() {
    try {
      await api.patchSettings(llm);
      setLlmDirty(false);
      toast.push(t("settings_page.llm_saved"), "ok");
    } catch (e) { toast.push(e.message, "err"); }
  }

  async function testLlm() {
    setLlmBusy(true);
    try {
      const r = await api.insightTest();
      toast.push(t("settings_page.llm_test_ok").replace("{model}", r.model || "?"), "ok");
    } catch (e) { toast.push(e.message, "err"); }
    finally { setLlmBusy(false); }
  }

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("nav.settings")}</h1></header>

      <section className="card">
        <div className="card-head"><h3>{t("settings_page.appearance")}</h3></div>
        <Field label={t("settings_page.theme")}>
          <div className="row" style={{gap:6}}>
            <button className={"chip" + (theme === "dark" ? " active" : "")} onClick={() => setTheme("dark")}>{t("settings_page.theme_dark")}</button>
            <button className={"chip" + (theme === "light" ? " active" : "")} onClick={() => setTheme("light")}>{t("settings_page.theme_light")}</button>
          </div>
        </Field>
        <Field label={t("settings_page.density")}>
          <div className="row" style={{gap:6}}>
            {["compact","regular","comfy"].map(d => (
              <button key={d} className={"chip" + (density === d ? " active" : "")} onClick={() => setDensity(d)}>{t("settings_page.density_" + d)}</button>
            ))}
          </div>
        </Field>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("settings_page.language")}</h3></div>
        <div className="row" style={{gap:6, flexWrap:"wrap"}}>
          {(locales?.locales || [{code:"en", native:"English"}]).map(l => (
            <button key={l.code} className={"chip" + (locale === l.code ? " active" : "")} onClick={() => setLocale(l.code)}>{l.native}</button>
          ))}
        </div>
        <p className="t-muted t-small" style={{marginTop:8}}>{t("settings_page.locale_hint")}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>{t("settings_page.llm")}</h3>
          <span className="t-muted t-small">{t("settings_page.llm_hint")}</span>
        </div>
        <Field label={t("settings_page.llm_base_url")} hint={t("settings_page.llm_base_url_hint")}>
          <input className="input t-mono" placeholder="https://api.openai.com/v1"
            value={llm.llm_base_url} onChange={e => setLlmField("llm_base_url", e.target.value)} />
        </Field>
        <Field label={t("settings_page.llm_model")} hint={t("settings_page.llm_model_hint")}>
          <input className="input t-mono" placeholder="gpt-4o-mini"
            value={llm.llm_model} onChange={e => setLlmField("llm_model", e.target.value)} />
        </Field>
        <Field label={t("settings_page.llm_api_key")} hint={t("settings_page.llm_api_key_hint")}>
          <input className="input t-mono" type="password" placeholder="sk-..."
            value={llm.llm_api_key} onChange={e => setLlmField("llm_api_key", e.target.value)} />
        </Field>

        <Field label={t("settings_page.llm_context_level")} hint={t("settings_page.llm_context_level_hint_" + llm.llm_context_level)}>
          <div className="row" style={{gap:6}}>
            {["full", "compact", "summary"].map(lvl => (
              <button key={lvl}
                className={"chip" + (llm.llm_context_level === lvl ? " active" : "")}
                onClick={() => setLlmField("llm_context_level", lvl)}>
                {t("settings_page.llm_context_level_" + lvl)}
              </button>
            ))}
          </div>
        </Field>

        <label className="row" style={{gap:8, alignItems:"center", marginTop:4, cursor:"pointer"}}>
          <input type="checkbox" checked={anonymizeOn}
            onChange={e => setLlmField("llm_anonymize", e.target.checked ? "true" : "false")} />
          <span>
            <div><b>{t("settings_page.llm_anonymize")}</b></div>
            <div className="t-muted t-small">{t("settings_page.llm_anonymize_hint")}</div>
          </span>
        </label>

        {isPublicProvider && !anonymizeOn && (
          <div className="err-panel" style={{marginTop:8, borderColor:"color-mix(in oklab, var(--warn) 40%, var(--line))",
            background:"color-mix(in oklab, var(--warn) 8%, var(--panel))", color:"var(--warn)"}}>
            <Icon.Alert /> <b>{t("settings_page.llm_public_warn_title").replace("{host}", isPublicProvider)}</b>
            <div style={{marginTop:4, fontFamily:"inherit"}}>{t("settings_page.llm_public_warn_body")}</div>
          </div>
        )}

        <div className="row" style={{gap:8, justifyContent:"flex-end", marginTop:8}}>
          <button className="btn ghost" onClick={testLlm} disabled={llmBusy}>
            {llmBusy ? <Spinner /> : <Icon.Check />} {t("settings_page.llm_test")}
          </button>
          <button className="btn primary" onClick={saveLlm} disabled={!llmDirty}>
            <Icon.Plus /> {t("common.save")}
          </button>
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("nav.system")}</h3></div>
        <dl className="kv">
          <dt>{t("settings_page.system_version")}</dt><dd className="t-mono">{health?.version || "—"}</dd>
          <dt>{t("settings_page.system_schema")}</dt><dd className="t-mono">{health?.schema || "—"}</dd>
          <dt>{t("settings_page.system_status")}</dt><dd>{health?.status === "ok" ? <span className="pill ok"><span className="dot"/>{t("settings_page.status_online")}</span> : <span className="pill warn">{t("settings_page.status_unknown")}</span>}</dd>
        </dl>
      </section>
    </div>
  );
}
