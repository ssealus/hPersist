// shell.jsx — app chrome only: Sidebar, Topbar, breadcrumb map.
// Widgets/charts/toasts/command-palette live in lib/.

function Sidebar({ route, go, counts, theme, setTheme }) {
  const items = [
    { section: t("nav.overview") },
    { id: "dashboard", label: t("nav.dashboard"), icon: "Dash" },
    { id: "inventories", label: t("nav.inventories"), icon: "Stack", badge: counts.inventories },
    { id: "servers", label: t("nav.all_servers"), icon: "Server", badge: counts.servers },
    { id: "addinv", label: t("nav.add_inventory"), icon: "Plus" },
    { section: t("nav.tools") },
    { id: "tool.scan",    label: t("tools.network_scanner"), icon: "Net" },
    { id: "tool.redfish", label: t("tools.redfish_tester"),  icon: "Term" },
    { section: t("nav.system") },
    { id: "stats",    label: t("nav.stats"),     icon: "Chart" },
    { id: "settings", label: t("nav.settings"),  icon: "Cog" },
  ];
  return (
    <aside className="sidebar app__sidebar scroll-y">
      <div className="sb-brand">
        {/* <img src="logo.svg" alt="hPersist" width="24" height="24"
             style={{flex: "0 0 24px", display: "block"}} /> */}
        <div className="sb-name">h<b>Persist</b></div>
        <div style={{marginLeft:"auto"}} className="t-micro">v0.0.1</div>
      </div>

      {items.map((it, i) => {
        if (it.section) return (
          <div className="sb-sect" key={"s"+i}>
            <span>{it.section}</span>
          </div>
        );
        const active = route.name === it.id || route.name.startsWith(it.id + ".");
        const Ic = window.Icon[it.icon];
        return (
          <a className={"sb-item" + (active ? " active" : "")} key={it.id}
             onClick={() => go(it.id)}>
            <Ic className="ico" />
            <span>{it.label}</span>
            {it.badge != null && <span className="badge t-num">{it.badge}</span>}
          </a>
        );
      })}

      <div className="sb-foot">
        <div style={{display:"flex", gap:6, marginTop: 8}}>
          <button className="btn ghost sm" style={{flex:1}} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Icon.Sun /> : <Icon.Moon />} {theme === "dark" ? t("settings_page.theme_light") : t("settings_page.theme_dark")}
          </button>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ route, go, openCommand }) {
  const crumbs = useCrumbs(route);
  return (
    <header className="topbar app__topbar">
      <div className="crumb">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            {c.to ? <a onClick={() => go(c.to)} style={{color:"inherit", cursor:"pointer"}}>{c.label}</a> : <b>{c.label}</b>}
          </React.Fragment>
        ))}
      </div>
      <div className="tb-spacer" />
      <div className="tb-search" onClick={openCommand}>
        <Icon.Search />
        <span>{t("app.search_placeholder")}</span>
      </div>
      {/* <button className="tb-iconbtn" title="Logs"><Icon.Logs /></button>
      <button className="tb-iconbtn" title="Refresh"><Icon.Refresh /></button> */}
      <button className="tb-btn primary" onClick={() => go("addinv")}>
        <Icon.Plus /> {t("nav.add_inventory")}
      </button>
    </header>
  );
}

function useCrumbs(route) {
  const map = {
    "dashboard": [{label:t("nav.dashboard")}],
    "inventories": [{label:t("nav.inventories")}],
    "inventories.detail": [{label:t("nav.inventories"), to:"inventories"}, {label: route.params?.name || "—"}],
    "servers": [{label:t("nav.all_servers")}],
    "server.detail": [{label:t("nav.all_servers"), to:"servers"}, {label: route.params?.name || "—"}],
    "addinv": [{label:t("nav.add_inventory")}],
    "addinv.local.cidr": [{label:t("nav.add_inventory"), to:"addinv"}, {label:"Local"}, {label:t("add_inventory.submode_cidr")}],
    "addinv.local.csv":  [{label:t("nav.add_inventory"), to:"addinv"}, {label:"Local"}, {label:t("add_inventory.submode_csv")}],
    "addinv.sh.generate":[{label:t("nav.add_inventory"), to:"addinv"}, {label:"Smart Hands"}, {label:t("add_inventory.submode_generate")}],
    "addinv.sh.process": [{label:t("nav.add_inventory"), to:"addinv"}, {label:"Smart Hands"}, {label:t("add_inventory.submode_process")}],
    "addinv.progress":   [{label:t("nav.add_inventory"), to:"addinv"}, {label:t("progress.title")}],
    "export.builder":    [{label:"Procurement export"}],
    "tool.scan":    [{label:t("nav.tools")}, {label:t("tools.network_scanner")}],
    "tool.redfish": [{label:t("nav.tools")}, {label:t("tools.redfish_tester")}],
    "stats":   [{label:t("nav.stats")}],
    "settings":[{label:t("nav.settings")}],
  };
  return map[route.name] || [{label: route.name}];
}
