// app.jsx — root, router, tweaks wiring

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "direction": "console",
  "density": "regular",
  "accent": "#00ff88",
  "showHelp": true
}/*EDITMODE-END*/;

const ACCENTS = [
  "#00ff88", // mint green (default)
  "#c8ff00", // electric lime
  "#4f7cff", // cobalt
  "#ff5c1a", // signal orange
  "#e8e1d3", // bone (monochrome accent)
];

function applyRoot(t) {
  const r = document.documentElement;
  r.setAttribute("data-theme", t.theme);
  r.setAttribute("data-direction", t.direction);
  r.setAttribute("data-density", t.density);
  // Apply accent dynamically for Console direction (Deck overrides accent)
  if (t.direction === "console") {
    r.style.setProperty("--accent", t.accent);
    if (t.theme === "light") {
      // For light theme, prefer slightly darker accent for contrast
      r.style.setProperty("--accent", `color-mix(in oklab, ${t.accent} 65%, oklch(0.45 0.15 150))`);
    } else {
      r.style.setProperty("--accent", t.accent);
    }
  } else {
    r.style.removeProperty("--accent");
  }
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  React.useEffect(() => applyRoot(t), [t]);

  const [locale, setLocaleState] = React.useState(window.i18n.code);

  React.useEffect(() => {
    api.getSettings().then(saved => {
      if (!saved) return;
      if (saved.locale && saved.locale !== window.i18n.code) {
        window.i18n.load(saved.locale).then(() => setLocaleState(saved.locale));
      }
      for (const k of ["theme", "direction", "density", "accent"]) {
        if (saved[k]) setTweak(k, saved[k]);
      }
    }).catch(() => {});
  }, []);

  async function changeLocale(code) {
    await window.i18n.load(code);
    setLocaleState(code);
    api.patchSettings({ locale: code }).catch(() => {});
  }

  function saveSetTweak(key, val) {
    setTweak(key, val);
    api.patchSettings({ [key]: val }).catch(() => {});
  }

  const [route, setRoute] = React.useState({ name: "dashboard", params: {} });
  const go = React.useCallback((name, params = {}) => {
    setRoute({ name, params });
    // Scroll main to top
    setTimeout(() => document.querySelector(".app__main")?.scrollTo(0, 0), 0);
  }, []);

  const [cmdOpen, setCmdOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdOpen(true); }
      if (e.key === "Escape") setCmdOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Sidebar badge counters — refreshed every 15s from /stats/fleet so they
  // stay live as collections complete or inventories are added/removed.
  const [counts, setCounts] = React.useState({ inventories: 0, servers: 0 });
  React.useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const d = await api.fleet();
        if (!cancelled) setCounts({
          inventories: d.totals?.inventories ?? 0,
          servers: d.totals?.servers ?? 0,
        });
      } catch {}
    };
    refresh();
    const id = setInterval(refresh, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [route.name]);

  // Map route to screen
  let screen = null;
  switch (route.name) {
    case "dashboard": screen = <Dashboard go={go} />; break;
    case "inventories": screen = <InventoriesList go={go} />; break;
    case "inventories.detail": screen = <InventoryDetail go={go} params={route.params} />; break;
    case "servers": screen = <AllServers go={go} />; break;
    case "server.detail": screen = <ServerDetail go={go} params={route.params} />; break;
    case "addinv": screen = <AddInventory go={go} />; break;
    case "addinv.local.cidr": screen = <LocalCidr go={go} />; break;
    case "addinv.local.csv": screen = <LocalCsv go={go} />; break;
    case "addinv.sh.generate": screen = <SmartHandsGen go={go} />; break;
    case "addinv.sh.process": screen = <SmartHandsProc go={go} />; break;
    case "addinv.progress": screen = <CollectionProgress go={go} params={route.params} />; break;
    case "export.builder": screen = <ExportBuilder go={go} params={route.params} />; break;
    case "tool.scan": screen = <ToolScan go={go} />; break;
    case "tool.redfish": screen = <ToolRedfish go={go} />; break;
    case "stats": screen = <Telemetry go={go} />; break;
    case "settings": screen = <Settings go={go}
                                          locale={locale} setLocale={changeLocale}
                                          theme={t.theme} setTheme={(v) => saveSetTweak("theme", v)}
                                          density={t.density} setDensity={(v) => saveSetTweak("density", v)}
                                          direction={t.direction} setDirection={(v) => saveSetTweak("direction", v)} />; break;
    default: screen = <Dashboard go={go} />;
  }

  return (
    <ToastProvider>
      <div className="app">
        <Topbar route={route} go={go} openCommand={() => setCmdOpen(true)} />
        <Sidebar route={route} go={go} counts={counts}
                 theme={t.theme} setTheme={(v) => saveSetTweak("theme", v)} />
        <main className="app__main scroll-y" key={route.name + JSON.stringify(route.params)}>
          {screen}
        </main>
      </div>

      <CommandPalette open={cmdOpen} close={() => setCmdOpen(false)} go={go} />

      <TweaksPanel title="Tweaks">
        <TweakSection label="Theme" />
        <TweakRadio label="Mode" value={t.theme} options={["dark","light"]} onChange={(v) => saveSetTweak("theme", v)} />
        <TweakRadio label="Direction" value={t.direction} options={[
          { value: "console", label: "Console" },
          { value: "deck", label: "Ops Deck" },
        ]} onChange={(v) => saveSetTweak("direction", v)} />
        <TweakColor label="Accent" value={t.accent} options={ACCENTS} onChange={(v) => saveSetTweak("accent", v)} />

        <TweakSection label="Layout" />
        <TweakRadio label="Density" value={t.density} options={["compact","regular","comfy"]} onChange={(v) => saveSetTweak("density", v)} />

        <TweakSection label="Navigate" />
        <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap: 6}}>
          {[
            ["dashboard","Dashboard"],
            ["addinv","Add inventory"],
            ["addinv.local.cidr","CIDR scan"],
            ["addinv.local.csv","CSV upload"],
            ["addinv.sh.generate","SH · generate"],
            ["addinv.sh.process","SH · process"],
            ["addinv.progress","Live progress"],
            ["inventories","Inventories"],
            ["servers","Servers"],
            ["export.builder","Export"],
            ["tool.scan","Tool · Scan"],
            ["tool.redfish","Tool · Redfish"],
            ["stats","Telemetry"],
            ["settings","Settings"],
          ].map(([r, l]) => (
            <button key={r} className={"chip" + (route.name === r ? " active" : "")} onClick={() => go(r)} style={{justifyContent:"center"}}>{l}</button>
          ))}
        </div>
      </TweaksPanel>
    </ToastProvider>
  );
}

window.__hPersistApp = App;
