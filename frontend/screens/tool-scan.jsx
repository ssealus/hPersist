// screens/tool-scan.jsx — network scanner as a standalone tool.
// Just wraps the CIDR scanner from add-local without the collection-start flow.

function ToolScan({ go }) {
  return <div className="screen">
    <header className="screen-head"><h1 className="t-h1">Network scanner</h1><p className="t-muted">Use this without committing to a full collection — just see what's out there.</p></header>
    <LocalCidr go={go} />
  </div>;
}
