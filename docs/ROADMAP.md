# hPersist — roadmap

Stuff that's been mocked up, scaffolded or imagined but **not** part of the
MVP. The plan is to ship a core first.

When implementing one of these, the flow is:

1. Add a module under `app/tools/<name>.py` with the business logic.
2. Add a route in `app/api/tools.py`.
3. Add an `api.<name>` method in `frontend/api.js`.
4. Add a screen component in `frontend/screens-rest.jsx`.
5. Add it into the sidebar (`frontend/shell.jsx`) and the router (`frontend/app.jsx`).
6. Add `tools.<key>` labels in `app/locales/en.json` + `ru.json`.
7. For new tables: `alembic revision --autogenerate -m "..."`.

---

## Deferred tools

### [ ] Part lookup
Search the fleet (and a bundled HPE catalog) for a part number, description
or serial. Originally had `app/tools/part_lookup.py`; removed pre-MVP to
keep the surface area small.

- Input: free-text, optional category filter.
- Output: rows with PN, category, description, how many times seen in local
  inventories, example servers (hostname/IP), manufacturer, source
  (`local` vs `catalog`).
- Open questions: source of truth for the catalog: bundle a snapshot vs
  pull from HPE PartSurfer on demand.

### [ ] Firmware compare
Roll up every server's installed firmware (BIOS, iLO, PSU, NIC, controllers)
and surface drift from a baseline catalog (`fw_baseline.json` shipped with
the app, possibly refreshed from HPE SPP).

- Columns: component, distinct installed versions w/ counts, latest known,
  affected hosts, severity (`current` / `outdated` / `critical`).
- Severity logic should consider known CVEs, not just version distance.
- Output also feeds the procurement export ("planned firmware upgrades").

### [ ] BOM diff
Compare bills-of-materials between two inventories — or two snapshots of
the same fleet over time. Quick way to spot stolen RAM, swapped drives,
or genuine ECO swaps after RMAs.

- Pick two inventories → diff at PN+location level.
- Categorise diffs: added / removed / replaced (same slot, different PN) /
  upgraded (same PN, capacity bump).
- Export the diff as CSV/XLSX for procurement and audit.

### [ ] License audit
Enumerate iLO / OneView entitlements across the
fleet and flag expirations or under-licensed hosts.

- Read iLO license info from Redfish `Managers/{id}/Oem/Hpe/License`.
- Track expiry dates in the DB, surface upcoming expirations.

### [ ] AI Insight
Get an AI summary or complex analytics based on your invenories.

- OpenAI Compatible API
- Modes: summmary, analytics, reports. 

---

## Beyond tools

### [ ] Multi-vendor support
Right now it is only about HPE iLO/Redfish-flavoured. Dell iDRAC, Lenovo XCC
and SuperMicro all speak Redfish but with different OEM extensions.
- Vendor detection in the walker, vendor-specific collector overrides.
- Per-vendor manager generation parsing (already factored that way in the
  manager collector).

### [ ] PostgreSQL testing
SQLite is the default for the workstation deploy. Settings already support `HPERSIST_DB__URL=postgresql://...`
and Alembic is wired in; needs real testing under load + per-dialect
quirks (no `render_as_batch`, FK enforcement, JSON column type, etc.).

### [ ] Scheduled collections
Cron-like config: re-collect inventory X every Y hours, alert on diffs.
- Background scheduler (`apscheduler` or hand-rolled).
- Per-inventory schedule stored in DB.
- Diff against the previous run, emit summary event.

### [ ] Auth + multi-tenancy
The MVP assumes a trusted single-user workstation deploy. For team use:
- Local user accounts + sessions.
- LDAP / SSO integration
- Per-user audit log on every mutating endpoint.
- Inventory ownership / sharing.

### [ ] Real-time fleet dashboard
Right now the dashboard polls. For sites that re-collect frequently, a
live websocket stream of fleet state changes would be nicer.

### [ ] Export templates
Save commonly-used `/exports` configurations (which sheets, columns, inventories).