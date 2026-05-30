// screens/settings.jsx — appearance + locale + system info.

function Settings({ locale, setLocale, theme, setTheme, density, setDensity, direction, setDirection }) {
  const [{ data: health }] = usePoll(() => api.get("/health"), []);
  const [{ data: locales }] = usePoll(() => api.locales(), []);

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("nav.settings")}</h1></header>

      <section className="card">
        <div className="card-head"><h3>{t("settings_page.appearance")}</h3></div>
        <Field label="Theme">
          <div className="row" style={{gap:6}}>
            <button className={"chip" + (theme === "dark" ? " active" : "")} onClick={() => setTheme("dark")}>Dark</button>
            <button className={"chip" + (theme === "light" ? " active" : "")} onClick={() => setTheme("light")}>Light</button>
          </div>
        </Field>
        <Field label="Density">
          <div className="row" style={{gap:6}}>
            {["compact","regular","comfy"].map(d => (
              <button key={d} className={"chip" + (density === d ? " active" : "")} onClick={() => setDensity(d)}>{d}</button>
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
        <p className="t-muted t-small" style={{marginTop:8}}>Drop new locale files into <code>app/locales/</code> and reload.</p>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("nav.system")}</h3></div>
        <dl className="kv">
          <dt>Version</dt><dd className="t-mono">{health?.version || "—"}</dd>
          <dt>Schema</dt><dd className="t-mono">{health?.schema || "—"}</dd>
          <dt>Status</dt><dd>{health?.status === "ok" ? <span className="pill ok"><span className="dot"/>online</span> : <span className="pill warn">unknown</span>}</dd>
        </dl>
      </section>
    </div>
  );
}
