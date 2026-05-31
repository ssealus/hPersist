// screens/tool-scan.jsx — network scanner as a standalone tool.
// Just wraps the CIDR scanner from add-local without the collection-start flow.

function ToolScan({ go }) {
  return <div className="screen">
    <header className="screen-head"><h1 className="t-h1">{t("tool_scan.title")}</h1><p className="t-muted">{t("tool_scan.subtitle")}</p></header>
    <LocalCidr go={go} />
  </div>;
}
