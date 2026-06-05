# Extending hPersist

Few things you might want to add.

## 1. New Redfish collector

```python
# app/redfish/collectors/indicators.py
from app.redfish.collectors.base import BaseCollector, ComponentRow, CollectorResult


class IndicatorsCollector(BaseCollector):
    name = "indicators"

    async def collect(self, client, system, chassis, manager) -> CollectorResult:
        indicators = await client.get(chassis.get("Indicators", {}).get("@odata.id"))
        rows: list[ComponentRow] = []
        for ind in indicators.get("Members", []):
            rows.append(ComponentRow(
                group="Indicator",
                label=ind.get("Name") or "Indicator",
                location=ind.get("Id"),
                health=(ind.get("Status") or {}).get("Health"),
                extra={"state": ind.get("IndicatorLED")},
            ))
        return CollectorResult(components=rows, summary={"indicator_count": len(rows)})
```

Register it:

```python
# app/redfish/collectors/__init__.py
from app.redfish.collectors.indicators import IndicatorsCollector

COLLECTORS = [
    SystemCollector(),
    ManagerCollector(),
    ProcessorCollector(),
    MemoryCollector(),
    StorageCollector(),
    NetworkCollector(),
    PCICollector(),
    PowerCollector(),
    IndicatorsCollector(),   # new
]
```

Walker picks it up automatically, components appear in the Server detail view, parts breakdown groups them, exports include them. No frontend changes needed.

### Mirror it into the Smart Hands template

If the customer site should also collect this group, it has to be added to `app/smart_hands/template/hpersist_collector/collectors.py` too — but **the SH collector uses a different shape than the main app** and the code can't be copied verbatim:

| | main app | SH template |
|---|---|---|
| File layout | one collector per file under `app/redfish/collectors/` | everything in a single `collectors.py` |
| Unit | `class IndicatorsCollector(BaseCollector)` with `async def collect(self, client, system, chassis, manager) -> CollectorResult` | `async def collect_indicators(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]` |
| Registry | `COLLECTORS: list[BaseCollector] = [..., IndicatorsCollector()]` | `COLLECTORS = [..., ("indicators", collect_indicators)]` |
| Return value | `CollectorResult(components=..., raw=..., summary=...)` | the literal tuple `(rows, raw, summary)` |

So the SH version of the example is:

```python
# inside app/smart_hands/template/hpersist_collector/collectors.py
async def collect_indicators(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    indicators = await client.get(chassis.get("Indicators", {}).get("@odata.id"))
    rows: list[ComponentRow] = []
    for ind in indicators.get("Members", []):
        rows.append(ComponentRow(
            group="Indicator",
            label=ind.get("Name") or "Indicator",
            location=ind.get("Id"),
            health=(ind.get("Status") or {}).get("Health"),
            extra={"state": ind.get("IndicatorLED")},
        ))
    return rows, {"Indicators": indicators}, {"indicator_count": len(rows)}


COLLECTORS = [
    # ... existing tuples …
    ("indicators", collect_indicators),
]
```

The generator picks up the whole template directory verbatim — only the source file shape has to match the SH walker's expectations.

## 2. New tool

Walk through adding a "License audit" tool end-to-end. The same recipe (and
the same six touch-points) applies to every other tool in `docs/ROADMAP.md`.

**1. Backend module.** Pure business logic, no FastAPI or React in here:

```python
# app/tools/license_audit/__init__.py  (or license_audit/audit.py — each tool lives in its own subdir)
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Server


@dataclass
class LicenseRow:
    server_id: str
    hostname: str | None
    tier: str | None
    expires: str | None


def audit(session: Session) -> list[LicenseRow]:
    rows = session.scalars(select(Server)).all()
    out = []
    for s in rows:
        lic = (s.raw_payload or {}).get("Manager", {}).get("Oem", {}).get("Hpe", {}).get("License", {})
        out.append(LicenseRow(
            server_id=s.id,
            hostname=s.hostname,
            tier=lic.get("LicenseType"),
            expires=lic.get("LicenseKey", {}).get("ExpiresAt"),
        ))
    return out
```

**2. Backend route.** Add to `app/api/tools.py`. The current file imports only `APIRouter`, `RedfishTestRequest` and `redfish_tester`, so the DB-aware imports must be added too:

```python
# app/api/tools.py
from fastapi import APIRouter, Depends            # add Depends
from sqlalchemy.orm import Session                # new
from app.db import get_session                    # new
from app.tools.redfish import tester as redfish_tester
from app.tools.license_audit import audit as license_audit  # new

# … existing routes …

@router.get("/license-audit")
def license_audit_route(session: Session = Depends(get_session)) -> list[dict]:
    return [
        {"server_id": r.server_id, "hostname": r.hostname, "tier": r.tier, "expires": r.expires}
        for r in license_audit.audit(session)
    ]
```

**3. Frontend API method** in `frontend/api.js`, alongside the other `api.<name>` entries:

```js
licenseAudit: () => api.get("/tools/license-audit"),
```

**4. Locale keys** in both `app/locales/en.json` and `app/locales/ru.json`, under the `tools` block:

```json
"tools": {
  "network_scanner": "Network scanner",
  "redfish_tester": "Redfish tester",
  "license_audit": "License audit"
}
```

**5. Screen component** at `frontend/screens/tool-license.jsx`. Use `usePoll` like the other tool screens for auto-refresh:

```jsx
function ToolLicense() {
  const [{ loading, data, error }] = usePoll(() => api.licenseAudit(), [], 30000);
  if (loading) return <div className="screen"><Spinner /></div>;
  if (error) return <div className="screen"><div className="err-panel">{error}</div></div>;
  return (
    <div className="screen">
      <header className="screen-head"><h1 className="t-h1">{t("tools.license_audit")}</h1></header>
      <table className="table">
        <thead><tr><th>Host</th><th>Tier</th><th>Expires</th></tr></thead>
        <tbody>
          {(data || []).map((r, i) => (
            <tr key={i}>
              <td className="t-mono">{r.hostname || r.server_id}</td>
              <td>{r.tier || "—"}</td>
              <td className="t-mono">{r.expires || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**6. Wire it into the shell.** Four spots:

- Register the screen in `frontend/index.html` load order, before `app.jsx`:
  ```html
  <script type="text/babel" src="screens/tool-license.jsx?v=N"></script>
  ```
- Sidebar item — `frontend/shell.jsx`, in the `items` array under the `t("nav.tools")` section:
  ```jsx
  { id: "tool.license", label: t("tools.license_audit"), icon: "Key" },
  ```
- Breadcrumb — same file, in the `map` table inside `useCrumbs`:
  ```jsx
  "tool.license": [{label:t("nav.tools")}, {label:t("tools.license_audit")}],
  ```
- Route — `frontend/app.jsx`, in the screen `switch`:
  ```jsx
  case "tool.license": screen = <ToolLicense go={go} />; break;
  ```

Bump the `?v=` cache-bust on `index.html` so the browser fetches the new JSX.

If the tool needs its own table, run `python -m alembic revision --autogenerate -m "add license audit table"` after declaring the model in `app/models.py` (see [ARCHITECTURE.md](ARCHITECTURE.md) for the model conventions). `start.bat` / `start.sh` applies pending migrations before launching uvicorn.

## 3. New locale

Drop a file:

```bash
cp app/locales/en.json app/locales/ru.json
```

Translate the values and keep keys identical. The top-level `_meta` block controls the display name in the language picker:

```json
{
  "_meta": { "name": "Russian", "native": "Русский", "code": "ru" },
  "app": { "name": "hPersist", ... },
  ...
}
```

`GET /api/v1/locales` lists everything in the directory; the Settings screen renders one chip per locale and `window.i18n.load(code)` swaps the pack at runtime — no rebuild, no restart.

Calling `t("nav.overview")` anywhere in the React tree reads from the active pack, falling back to the literal key if a string is missing.

## 4. New export format

For example PDF

```python
# app/exports/pdf.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.exports.builder import ExportSheet


def render_pdf(sheets: list[ExportSheet], title: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    for sheet in sheets:
        y -= 24
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, sheet.name)
        c.setFont("Helvetica", 9)
        # ExportSheet.rows is list[list] (positional, aligned with sheet.columns),
        # not list[dict] — iterate the row directly.
        for row in sheet.rows[:30]:   # truncate for the example
            y -= 12
            c.drawString(60, y, " · ".join(str(v) for v in row)[:120])
        c.showPage()
    c.save()
    return buf.getvalue()
```

Add it in `app/api/exports.py`:

```python
elif req.format == "pdf":
    data = render_pdf(sheets, filename_base)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'})
```

Add `"pdf"` to the schema's regex (`app/api/schemas.py:ExportRequest.format`) and surface it in the Export builder dropdown (`frontend/screens/export.jsx:ExportBuilder`).
