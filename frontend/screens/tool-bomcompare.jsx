// screens/tool-bomcompare.jsx — diff BOMs between two inventories.

function ToolBomCompare() {
  const [inventories, setInventories] = React.useState([]);
  const [a, setA] = React.useState("");
  const [b, setB] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [tab, setTab] = React.useState("added");
  const toast = useToast();

  React.useEffect(() => {
    api.inventories().then(rs => setInventories(rs || []));
  }, []);

  async function run() {
    if (!a || !b) { toast.push(t("bomcompare.toast_pick_both"), "err"); return; }
    if (a === b)  { toast.push(t("bomcompare.toast_same"), "err"); return; }
    setBusy(true);
    try {
      const r = await api.bomCompare(a, b);
      setResult(r);
      // Auto-jump to the first non-empty tab so the user sees signal immediately.
      for (const k of ["replaced", "upgraded", "added", "removed"]) {
        if (r.summary[k] > 0) { setTab(k); break; }
      }
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  // For each server-level diff, return only the rows for the active tab.
  const rowsForTab = React.useMemo(() => {
    if (!result) return [];
    const out = [];
    for (const sd of result.server_diffs) {
      for (const item of (sd[tab] || [])) {
        out.push({ ...item, hostname: sd.hostname, sn: sd.serial_number, model: sd.model });
      }
    }
    return out;
  }, [result, tab]);

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{t("tools.bom_compare")}</h1>
          <p className="t-muted">{t("bomcompare.subtitle")}</p>
        </div>
      </header>

      <section className="card">
        <div className="card-head"><h3>{t("bomcompare.section_pick")}</h3></div>
        <div className="grid grid-2" style={{gap:12}}>
          <Field label={t("bomcompare.field_a")} hint={t("bomcompare.field_a_hint")}>
            <select className="input" value={a} onChange={e => setA(e.target.value)}>
              <option value="">{t("bomcompare.select_placeholder")}</option>
              {inventories.map(inv => (
                <option key={inv.id} value={inv.id}>{inv.name} · {inv.servers} {t("bomcompare.servers_suffix")}</option>
              ))}
            </select>
          </Field>
          <Field label={t("bomcompare.field_b")} hint={t("bomcompare.field_b_hint")}>
            <select className="input" value={b} onChange={e => setB(e.target.value)}>
              <option value="">{t("bomcompare.select_placeholder")}</option>
              {inventories.map(inv => (
                <option key={inv.id} value={inv.id}>{inv.name} · {inv.servers} {t("bomcompare.servers_suffix")}</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="row" style={{marginTop:12, gap:8, justifyContent:"flex-end"}}>
          <button className="btn primary" onClick={run} disabled={busy || !a || !b}>
            {busy ? <Spinner /> : <Icon.Diff />} {t("bomcompare.compare")}
          </button>
        </div>
      </section>

      {!result && !busy && (
        <section className="card"><Empty msg={t("bomcompare.no_result_yet")} /></section>
      )}

      {result && (
        <>
          <section className="kpi-row">
            <Kpi label={t("bomcompare.kpi_added")}    value={result.summary.added} />
            <Kpi label={t("bomcompare.kpi_removed")}  value={result.summary.removed} />
            <Kpi label={t("bomcompare.kpi_replaced")} value={result.summary.replaced} />
            <Kpi label={t("bomcompare.kpi_upgraded")} value={result.summary.upgraded} />
            <Kpi label={t("bomcompare.kpi_servers_changed")} value={result.summary.servers_changed} />
            <Kpi label={t("bomcompare.kpi_only_a")}   value={result.summary.servers_only_in_a} />
            <Kpi label={t("bomcompare.kpi_only_b")}   value={result.summary.servers_only_in_b} />
          </section>

          <nav className="tabs">
            {[
              { id: "added",    label: t("bomcompare.tab_added"),    n: result.summary.added },
              { id: "removed",  label: t("bomcompare.tab_removed"),  n: result.summary.removed },
              { id: "replaced", label: t("bomcompare.tab_replaced"), n: result.summary.replaced },
              { id: "upgraded", label: t("bomcompare.tab_upgraded"), n: result.summary.upgraded },
              { id: "servers",  label: t("bomcompare.tab_servers"),  n: result.summary.servers_only_in_a + result.summary.servers_only_in_b },
            ].map(it => (
              <button key={it.id} className={"tab" + (tab === it.id ? " active" : "")} onClick={() => setTab(it.id)}>
                {it.label} <span className="t-muted t-num">{it.n}</span>
              </button>
            ))}
          </nav>

          {(tab === "added" || tab === "removed") && (
            rowsForTab.length === 0 ? <Empty msg={t("bomcompare.tab_empty")} /> :
            <section className="card">
              <table className="table compact">
                <thead><tr>
                  <th>{t("bomcompare.col_server")}</th>
                  <th>{t("bomcompare.col_group")}</th>
                  <th>{t("bomcompare.col_location")}</th>
                  <th>{t("bomcompare.col_pn")}</th>
                  <th>{t("bomcompare.col_label")}</th>
                  <th>{t("bomcompare.col_capacity")}</th>
                </tr></thead>
                <tbody>
                  {rowsForTab.map((r, i) => (
                    <tr key={i}>
                      <td><b>{r.hostname || "—"}</b><div className="t-muted t-mono t-small">{r.sn}</div></td>
                      <td><span className="pill outline">{r.group}</span></td>
                      <td className="t-mono t-muted">{r.location || "—"}</td>
                      <td className="t-mono">{r.part_number || "—"}</td>
                      <td className="t-muted" style={{maxWidth:340, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{r.label}</td>
                      <td className="t-num t-muted">{r.capacity_value ? `${r.capacity_value} ${r.capacity_unit || ""}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {(tab === "replaced" || tab === "upgraded") && (
            rowsForTab.length === 0 ? <Empty msg={t("bomcompare.tab_empty")} /> :
            <section className="card">
              <table className="table compact">
                <thead><tr>
                  <th>{t("bomcompare.col_server")}</th>
                  <th>{t("bomcompare.col_group")}</th>
                  <th>{t("bomcompare.col_location")}</th>
                  <th>{t("bomcompare.col_before")}</th>
                  <th>{t("bomcompare.col_after")}</th>
                </tr></thead>
                <tbody>
                  {rowsForTab.map((r, i) => (
                    <tr key={i}>
                      <td><b>{r.hostname || "—"}</b><div className="t-muted t-mono t-small">{r.sn}</div></td>
                      <td><span className="pill outline">{r.before.group}</span></td>
                      <td className="t-mono t-muted">{r.before.location || "—"}</td>
                      <td>
                        <div className="t-mono">{r.before.part_number || "—"}</div>
                        <div className="t-muted t-small">{r.before.label}{r.before.capacity_value ? ` · ${r.before.capacity_value} ${r.before.capacity_unit || ""}` : ""}</div>
                      </td>
                      <td>
                        <div className="t-mono" style={{color: tab === "upgraded" ? "var(--accent)" : "inherit"}}>{r.after.part_number || "—"}</div>
                        <div className="t-muted t-small">{r.after.label}{r.after.capacity_value ? ` · ${r.after.capacity_value} ${r.after.capacity_unit || ""}` : ""}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {tab === "servers" && (
            <section className="grid grid-2">
              <div className="card">
                <div className="card-head"><h3>{t("bomcompare.only_in_a").replace("{name}", result.inventory_a.name)}</h3></div>
                {result.servers_only_in_a.length === 0 ? <Empty msg={t("bomcompare.tab_empty")} /> :
                  <table className="table compact"><tbody>
                    {result.servers_only_in_a.map(s => (
                      <tr key={s.id}><td><b>{s.hostname || "—"}</b></td><td className="t-mono t-muted">{s.serial_number}</td><td className="t-muted">{s.model}</td></tr>
                    ))}
                  </tbody></table>
                }
              </div>
              <div className="card">
                <div className="card-head"><h3>{t("bomcompare.only_in_b").replace("{name}", result.inventory_b.name)}</h3></div>
                {result.servers_only_in_b.length === 0 ? <Empty msg={t("bomcompare.tab_empty")} /> :
                  <table className="table compact"><tbody>
                    {result.servers_only_in_b.map(s => (
                      <tr key={s.id}><td><b>{s.hostname || "—"}</b></td><td className="t-mono t-muted">{s.serial_number}</td><td className="t-muted">{s.model}</td></tr>
                    ))}
                  </tbody></table>
                }
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
