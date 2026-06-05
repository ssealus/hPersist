# hPersist

Hardware inventory collector for HPE servers. Sweeps a subnet over Redfish,
pulls every component down to the DIMM-slot level, and produces audit-ready
exports (XLSX / CSV / JSON). Also ships a **Smart Hands** workflow for sites
you can't reach yourself: a portable archive an on-site engineer runs,
signs, and ships back.

> [!WARNING]
> **Pre-1.0, active development.** hPersist is built and tested with the
> [HPE iLO Redfish Emulator](https://github.com/HewlettPackard/ilo-redfish-emulator)
> with mockups for `DL360`, `DL380a`, `DL365 Gen10 Plus`, `DL380a Gen12` and
> `Cray EX235a`. It has **not** been validated against real iLO hardware in
> production yet. Try it on a staging rack first.
>
> No warranty, express or implied. Found a bug or want a feature? Open an
> issue. Want to help us calibrate the collector across iLO firmware revs we
> can't test against? Settings → Telemetry → Export pulls a fully
> anonymised rollup — share it (DM, issue or email) and it goes
> straight into our regression matrix.

![hPersist dashboard](docs/screenshots/dashboard.png)

## What it does

- **Collect.** Sweep a CIDR or upload a CSV of iLO endpoints. The async
  runner walks Redfish (`Systems`, `Chassis`, `Managers` + sub-resources) for
  every host in parallel with a bounded concurrency cap. Discovery uses
  collection enumeration + `System.Links` — so it works on classic ProLiant
  trees and on Cray EX-style multi-chassis blades alike.
- **Catalog.** System summary, BIOS, iLO generation + firmware, CPUs
  (model / cores / threads), DIMMs (capacity / speed / rank / slot), drives
  (capacity / media / firmware), NICs (ports / speeds / MACs), PSUs (rated
  watts / model), PCIe devices. Plus the raw Redfish payload kept verbatim
  in `Server.raw_payload` for forensics.
- **Analyze.** Live WebSocket progress, fleet rollups, model treemap, iLO
  firmware drift, health bucketing, parts breakdown with HPE PN aggregation.
- **Export.** XLSX (multi-sheet), CSV, JSON. Optional anonymisation strips
  serial numbers, IPs, and hostnames so the file is safe to share with
  procurement or vendors.
- **Smart Hands.** A self-contained tarball with `collect.py` that runs
  offline at a customer site. Returns a `results.hpr` envelope with
  per-host hash chain + ed25519 signatures. Tampered scripts surface as
  warnings — non-blocking, but visible.
- **Telemetry.** Local rollup of timings, hardware shapes, success rates.
  Opt-in export for benchmark sharing (see [Privacy](#privacy) below).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  uvicorn (asyncio event loop)                                   │
│                                                                 │
│   FastAPI app (app/main.py)                                     │
│   ├─ REST routes under /api/v1/...                              │
│   ├─ WebSocket /ws/jobs/{inventory_id}                          │
│   └─ SPA fallback serves frontend/index.html + assets           │
│                                                                 │
│   In-process job runner (app/jobs/runner.py)                    │
│   ├─ asyncio.Semaphore caps concurrency                         │
│   ├─ EventBus (asyncio.Queue per channel) → WebSocket           │
│   └─ Each host: probe → walk Redfish → persist                  │
│                                                                 │
│   SQLite / Postgres (app/db.py)                                 │
│   └─ <project>/data/hpersist.db or HPERSIST_DB__URL=...         │
└─────────────────────────────────────────────────────────────────┘
```

Single Python process, embedded SQLite by default or external Postgres.
The frontend is React + JSX served through in-browser Babel — no `npm`,
no bundler, no build step. Full deep dive in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
app/
├── api/             HTTP routes
├── jobs/            Background runner + WebSocket bus
├── redfish/         Async client + per-component collectors
├── network/         CIDR scanner, CSV parser
├── smart_hands/     Archive generator + envelope processor + template/
├── analytics/       Inventory and fleet aggregations
├── exports/         XLSX / CSV / JSON builders
├── tools/           Redfish tester (history persisted in SQLite)
├── stats/           Telemetry rollups
└── core/            DB, logging, integrity (ed25519 + hash chain)
```

## Run it

### Docker (recommended for ops)

```bash
docker build -t hpersist:latest .

docker volume create hpersist_data
docker run -d --name hpersist \
    -p 8765:8765 \
    -v hpersist_data:/data \
    --add-host=host.docker.internal:host-gateway \
    hpersist:latest
```

Open <http://localhost:8765>. Migrations are applied automatically on
container start; the named volume persists the SQLite DB, logs, and
archives across container rebuilds.

The image is single-stage, non-root (uid 10001), `tini` as PID 1 so
`docker stop` reaches uvicorn cleanly. ~300 MB.

### Local (venv, for development)

Requires Python 3.11+.

```bash
git clone <this-repo> hpersist && cd hpersist
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate            # Windows PowerShell

pip install -r requirements.txt
bash start.sh                     # Linux / macOS
# start.bat                        # Windows
```

`start.sh` runs `alembic upgrade head`, then launches uvicorn on port 8765.
Ctrl-C to stop. Data lands in `<project>/data/`.

### Postgres backend

For multi-user or large fleets, point at Postgres instead of SQLite:

```env
# .env at the project root
HPERSIST_DB__URL=postgresql+psycopg://user:pass@host:5432/hpersist
HPERSIST_DB__POOL_SIZE=20
```

The Postgres driver (`psycopg[binary]`) is already in `requirements.txt`.
No migration changes needed — Alembic emits dialect-correct DDL on either
backend (and we test both in CI).

## Configure

All settings are env-driven via pydantic-settings. Prefix `HPERSIST_`,
nested groups joined with `__`. The common ones:

| Variable | Default | Purpose |
|---|---|---|
| `HPERSIST_SERVER__HOST` | `127.0.0.1` | Bind address |
| `HPERSIST_SERVER__PORT` | `8765` | Bind port |
| `HPERSIST_SERVER__LOG_LEVEL` | `info` | uvicorn log level |
| `HPERSIST_DATA_DIR` | `./data` | Logs, archives, uploads, SQLite |
| `HPERSIST_DB__URL` | `sqlite:///./data/hpersist.db` | SQLAlchemy URL |
| `HPERSIST_DB__POOL_SIZE` | `5` | Connection pool size |
| `HPERSIST_COLLECTOR__CONCURRENCY` | `16` | Parallel host walks |
| `HPERSIST_COLLECTOR__TIMEOUT_SECONDS` | `8` | Per-host HTTP timeout |
| `HPERSIST_COLLECTOR__TLS_VERIFY` | `warn-only` | `strict` / `warn-only` / `off` |
| `HPERSIST_LOG__RETENTION_DAYS` | `90` | File log retention |
| `HPERSIST_CORS__ALLOW_ORIGINS` | `["*"]` | JSON array |

Full catalogue with defaults and notes in [.env.example](.env.example).

## Privacy

> [!IMPORTANT]
> **Nothing leaves your machine without your action.**
>
> - hPersist makes **zero outbound connections** during use. No
>   phone-home, no analytics SDK, no auto-update check.
> - Collected inventory data stays in the local SQLite (or your Postgres
>   instance). The Smart Hands tarball and the returned `results.hpr`
>   envelope move over whatever channel you choose — hPersist itself does
>   not upload them anywhere.
> - **Anonymised telemetry** (Settings → Telemetry → Export) is local,
>   opt-in, and contains zero identifying data. The JSON includes only
>   counts, percentiles, buckets, and public catalog identifiers (model
>   names, HPE part numbers). It never includes hostnames, IPs, MACs,
>   serial numbers, organisations, descriptions, raw Redfish payloads, or
>   credentials. See `app/stats/telemetry.py` — the whitelist is the
>   source of truth.
> - Sharing the telemetry export with maintainers (DM, GitHub issue,
>   email) helps calibrate the collector across iLO firmware
>   revisions we don't have hardware to test against. Review the JSON
>   before sending if you want to be sure.

## Tools

The MVP ships **Network scanner**, **Redfish tester**,
**AI Insight** (OpenAI-compatible LLM analysis of selected inventories —
configure base URL / API key / model in Settings), **PartSurfer search**
(HPE Spare BOM lookup by SN/PN/model with a 7-day DB cache; deep-link from
any server-detail page) and **BOM Compare** (diff two inventories at
group/location/PN — added/removed/replaced/upgraded per server).
Deferred tools like Firmware compare are in [docs/ROADMAP.md](docs/ROADMAP.md).

## Extending

Adding a new collector / locale / export format / tool is a single-file
affair. See [docs/EXTENDING.md](docs/EXTENDING.md) for the four most
common recipes with working code samples and the file you have to touch
for each.

## Roadmap

Multi-vendor (Dell iDRAC / Lenovo XCC / SuperMicro), scheduled
re-collections, auth + multi-tenancy, the deferred tools above, and more.
Full list in [docs/ROADMAP.md](docs/ROADMAP.md).

## Feedback

Found a bug, want a feature, hit a real iLO that doesn't behave like the
emulator? Open an issue. PRs welcome.

## License

Apache-2.0. See [LICENSE](LICENSE).
