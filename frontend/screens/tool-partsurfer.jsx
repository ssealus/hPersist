// screens/tool-partsurfer.jsx — HPE PartSurfer search: SN/PN/model → Spare BOM table.

function ToolPartSurfer({ params }) {
  const [query, setQuery] = React.useState(params?.q || "");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [filter, setFilter] = React.useState("");
  const [sortKey, setSortKey] = React.useState(null);
  const [sortDir, setSortDir] = React.useState("asc");
  const toast = useToast();

  // Auto-fire when arriving with a pre-filled query (e.g. deep-link from server detail).
  const initialRanRef = React.useRef(false);
  React.useEffect(() => {
    if (params?.q && !initialRanRef.current) {
      initialRanRef.current = true;
      run(params.q);
    }
  }, [params?.q]);

  async function run(q = query, force = false) {
    if (!q || q.trim().length < 2) { toast.push(t("partsurfer.toast_too_short"), "err"); return; }
    setBusy(true);
    try {
      const r = await api.partsurferSearch(q.trim(), force);
      setResult(r);
      if (r.not_found) toast.push(t("partsurfer.toast_not_found").replace("{q}", q), "warn");
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  function sortBy(key) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(
      () => toast.push(t("partsurfer.toast_copied").replace("{text}", text), "ok"),
      () => {},
    );
  }

  const rows = React.useMemo(() => {
    if (!result?.spare_bom) return [];
    let out = result.spare_bom;
    if (filter) {
      const f = filter.toLowerCase();
      out = out.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(f)));
    }
    if (sortKey) {
      const cmp = (a, b) => {
        const va = String(a[sortKey] || ""); const vb = String(b[sortKey] || "");
        const numA = Number(va); const numB = Number(vb);
        if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
        return va.localeCompare(vb);
      };
      out = [...out].sort((a, b) => sortDir === "asc" ? cmp(a, b) : -cmp(a, b));
    }
    return out;
  }, [result, filter, sortKey, sortDir]);

  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <h1 className="t-h1">{t("tools.partsurfer")}</h1>
          <p className="t-muted">{t("partsurfer.subtitle")}</p>
        </div>
      </header>

      <section className="card">
        <div className="card-head"><h3>{t("partsurfer.section_search")}</h3></div>
        <div className="row" style={{gap:8, alignItems:"end"}}>
          <Field label={t("partsurfer.field_query")} style={{marginBottom: 0}}>
            <input className="input t-mono" placeholder={t("partsurfer.field_query_placeholder")}
              value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && run()} />
          </Field>
          <button className="btn primary" style={{height: 30}} onClick={() => run()} disabled={busy}>
            {busy ? <Spinner /> : <Icon.Search />} {t("partsurfer.search")}
          </button>
          {result && (
            <button className="btn ghost" style={{height: 30}} onClick={() => run(query, true)} disabled={busy}
                    title={t("partsurfer.refresh_tooltip")}>
              <Icon.Refresh /> {t("partsurfer.refresh")}
            </button>
          )}
        </div>
        <div className="field-hint t-muted" style={{marginTop:6}}>{t("partsurfer.field_query_hint")}</div>
      </section>

      {busy && !result && (
        <section className="card"><div className="empty"><Spinner /> <span className="t-muted">{t("partsurfer.fetching")}</span></div></section>
      )}

      {result && !result.not_found && Object.keys(result.product || {}).length > 0 && (
        <section className="card">
          <div className="card-head">
            <h3>{t("partsurfer.section_product")}</h3>
            <span className="t-muted t-small">
              {result.meta?.cached
                ? <><span className="pill ok"><span className="dot"/>{t("partsurfer.cached")}</span> {result.meta.fetched_at}</>
                : <span className="pill outline">{t("partsurfer.live")}</span>}
            </span>
          </div>
          <dl className="kv">
            {result.product.serial_number && (<><dt>{t("partsurfer.product_sn")}</dt><dd className="t-mono">{result.product.serial_number}</dd></>)}
            {result.product.product_number && (<><dt>{t("partsurfer.product_pn")}</dt><dd className="t-mono">{result.product.product_number}</dd></>)}
            {result.product.description && (<><dt>{t("partsurfer.product_desc")}</dt><dd>{result.product.description}</dd></>)}
            {result.product.rohs_status && (<><dt>{t("partsurfer.product_rohs")}</dt><dd className="t-mono">{result.product.rohs_status}</dd></>)}
          </dl>
        </section>
      )}

      {result && !result.not_found && Object.keys(result.product || {}).length > 0 && result.spare_bom?.length === 0 && (
        <section className="card">
          <div className="t-muted t-small">{t("partsurfer.spare_pn_terminal")}</div>
        </section>
      )}

      {result && !result.not_found && result.spare_bom?.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h3>{t("partsurfer.section_sbom")} <span className="t-muted t-num">({result.spare_bom.length})</span></h3>
            <input className="input" style={{maxWidth: 240}} placeholder={t("partsurfer.filter_placeholder")}
              value={filter} onChange={e => setFilter(e.target.value)} />
          </div>
          <table className="table compact">
            <thead><tr>
              {[
                ["spare_part_number", t("partsurfer.col_pn")],
                ["spare_part_description", t("partsurfer.col_desc")],
                ["category", t("partsurfer.col_category")],
                ["most_used", t("partsurfer.col_most_used")],
                ["csr", t("partsurfer.col_csr")],
                ["rohs", t("partsurfer.col_rohs")],
                ["m_part_number", t("partsurfer.col_master_pn")],
              ].map(([k, label]) => (
                <th key={k} onClick={() => sortBy(k)} style={{cursor:"pointer", userSelect:"none"}}>
                  {label}{sortKey === k ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="t-mono row-clickable" onClick={() => copyToClipboard(r.spare_part_number)}
                      title={t("partsurfer.click_to_copy")}>{r.spare_part_number}</td>
                  <td>{r.spare_part_description}</td>
                  <td className="t-muted">{r.category}</td>
                  <td className="t-num t-muted">{r.most_used}</td>
                  <td className="t-muted">{r.csr}</td>
                  <td className="t-mono t-muted">{r.rohs}</td>
                  <td className="t-mono t-muted">{r.m_part_number}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {result?.not_found && (
        <section className="card">
          <div className="empty">
            <Icon.Alert />
            <div><b>{t("partsurfer.not_found_title").replace("{q}", result.query || query)}</b></div>
            <div className="t-muted t-small" style={{marginTop:8, maxWidth:540}}>
              {t("partsurfer.not_found_hint")}
            </div>
            <a className="t-muted t-small" target="_blank" rel="noopener"
               href={`https://partsurfer.hpe.com/Search.aspx?searchText=${encodeURIComponent(result.query || query)}`}>
              {t("partsurfer.open_in_partsurfer")} ↗
            </a>
          </div>
        </section>
      )}

      {!result && !busy && (
        <section className="card">
          <Empty msg={t("partsurfer.no_search_yet")} />
        </section>
      )}
    </div>
  );
}
