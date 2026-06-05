// screens/export.jsx — procurement export builder.

function ExportBuilder({ params }) {
  const [{ data: inventories }] = usePoll(() => api.inventories(), []);
  const [selected, setSelected] = React.useState(new Set(params?.inventory_ids || []));
  const [layout, setLayout] = React.useState("flat");
  const [format, setFormat] = React.useState("xlsx");
  const [groups, setGroups] = React.useState(new Set(["System","CPU","DIMM","Drive","Controller","NIC","Port","PCIe","PSU"]));
  const [anonymize, setAnonymize] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const toast = useToast();

  function toggleInv(id) { setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; }); }
  function toggleGroup(g) { setGroups(s => { const n = new Set(s); n.has(g) ? n.delete(g) : n.add(g); return n; }); }

  async function run() {
    if (selected.size === 0) { toast.push(t("export.toast_pick_inventory"), "err"); return; }
    setBusy(true);
    try {
      const { blob, filename } = await api.exportBlob({
        inventory_ids: [...selected],
        format, layout, anonymize,
        groups: [...groups],
      });
      downloadBlob(blob, filename || `hpersist-export.${format}`);
      toast.push(t("export.toast_downloaded"), "ok");
    } catch (e) { toast.push(e.message, "err"); }
    finally { setBusy(false); }
  }

  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("export.title")}</h1></header>

      <section className="card">
        <div className="card-head"><h3>{t("export.step_choose_inventories")}</h3><span className="t-muted">{t("export.selected_count").replace("{count}", selected.size)}</span></div>
        <div className="grid grid-2" style={{gap:8}}>
          {(inventories || []).map(i => (
            <label key={i.id} className={"opt-card " + (selected.has(i.id) ? "selected" : "")}>
              <input type="checkbox" checked={selected.has(i.id)} onChange={() => toggleInv(i.id)} />
              <div>
                <b>{i.name}</b><div className="t-muted t-small">{i.organization || "—"} · {t("export.inv_card_servers").replace("{count}", i.servers)}</div>
              </div>
            </label>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h3>{t("export.step_format_layout")}</h3></div>
        <div className="grid grid-2">
          <Field label={t("export.field_format")}>
            <select className="input" value={format} onChange={e => setFormat(e.target.value)}>
              <option value="xlsx">{t("export.format_xlsx")}</option>
              <option value="csv">{t("export.format_csv")}</option>
              <option value="json">{t("export.format_json")}</option>
            </select>
          </Field>
          <Field label={t("export.field_layout")}>
            <select className="input" value={layout} onChange={e => setLayout(e.target.value)}>
              <option value="flat">{t("export.layout_flat")}</option>
              <option value="by_server">{t("export.layout_by_server")}</option>
              <option value="by_part">{t("export.layout_by_part")}</option>
            </select>
          </Field>
        </div>

        <Field label={t("export.field_component_groups")} style={{marginTop:12}}>
          <div className="row" style={{flexWrap:"wrap", gap: 6}}>
            {["System","CPU","DIMM","Drive","Controller","NIC","Port","PCIe","PSU"].map(g => (
              <button key={g} className={"chip" + (groups.has(g) ? " active" : "")} onClick={() => toggleGroup(g)}>{g}</button>
            ))}
          </div>
        </Field>

        <Field label={t("export.field_anonymize")} style={{marginTop:12}}>
          <label className="row" style={{gap:6}}><input type="checkbox" checked={anonymize} onChange={e => setAnonymize(e.target.checked)} /> {t("export.anonymize_toggle_label")}</label>
        </Field>

        <div className="row" style={{marginTop:12, justifyContent:"flex-end"}}>
          <button className="btn primary" onClick={run} disabled={busy || selected.size === 0}><Icon.Download /> {t("export.download_btn").replace("{format}", format.toUpperCase())}</button>
        </div>
      </section>
    </div>
  );
}
