// screens/add-inventory.jsx — landing page for the 4 collection flows.

function AddInventory({ go }) {
  return (
    <div className="screen">
      <header className="screen-head">
        <h1 className="t-h1">{t("add_inventory.title")}</h1>
        <p className="t-muted">{t("add_inventory.subtitle")}</p>
      </header>

      <section className="grid grid-2">
        <div className="card mode-card">
          <div className="mode-head"><Icon.Net /> <h2>{t("add_inventory.mode_local")}</h2></div>
          <p className="t-muted">{t("add_inventory.mode_local_desc")}</p>
          <div className="grid grid-2" style={{marginTop: 12, gap: 8}}>
            <button className="mode-btn" onClick={() => go("addinv.local.cidr")}>
              <Icon.Net size={16} /> <div><b>{t("add_inventory.submode_cidr")}</b><div className="t-muted t-small">{t("add_inventory.submode_cidr_desc")}</div></div>
            </button>
            <button className="mode-btn" onClick={() => go("addinv.local.csv")}>
              <Icon.Doc size={16} /> <div><b>{t("add_inventory.submode_csv")}</b><div className="t-muted t-small">{t("add_inventory.submode_csv_desc")}</div></div>
            </button>
          </div>
        </div>

        <div className="card mode-card">
          <div className="mode-head"><Icon.Stack /> <h2>{t("add_inventory.mode_smart_hands")}</h2></div>
          <p className="t-muted">{t("add_inventory.mode_smart_hands_desc")}</p>
          <div className="grid grid-2" style={{marginTop: 12, gap: 8}}>
            <button className="mode-btn" onClick={() => go("addinv.sh.generate")}>
              <Icon.Download size={16} /> <div><b>{t("add_inventory.submode_generate")}</b><div className="t-muted t-small">{t("add_inventory.submode_generate_desc")}</div></div>
            </button>
            <button className="mode-btn" onClick={() => go("addinv.sh.process")}>
              <Icon.Layers size={16} /> <div><b>{t("add_inventory.submode_process")}</b><div className="t-muted t-small">{t("add_inventory.submode_process_desc")}</div></div>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
