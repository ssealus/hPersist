# hPersist — architecture

A single Python process, an embedded SQLite database, and a Babel-served React frontend. Designed to run on a workstation or a small VM, no external services.

## Process model

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
│   ├─ asyncio.Semaphore to cap concurrency                       │
│   ├─ EventBus (asyncio.Queue per channel) → WebSocket           │
│   └─ Each host: probe → walk Redfish → persist                  │
│                                                                 │
│   SQLite (app/db.py)                                            │
│   ├─ WAL journal, busy_timeout=15s, foreign keys                │
│   └─ <project>/data/hpersist.db                                 │
└─────────────────────────────────────────────────────────────────┘
```

The whole thing runs in **one process**. No Celery, no Redis, no broker. Jobs live as asyncio tasks; the event loop dispatches WebSocket frames as fast as collectors produce them. The trade-off is intentional: hPersist is an operator's tool, not a multi-tenant SaaS.

## Data flow — local collection

1. **POST /api/v1/collections** with mode `cidr` or `csv` + selected hosts.
2. Route creates an `Inventory` row (`status=in-progress`, `submode=cidr|csv`) and schedules a background coroutine.
3. The runner walks the host list with `asyncio.Semaphore(concurrency)`.
4. For each host the `RedfishClient` opens an authenticated session, probes `/redfish/v1/`, then `walker.collect_host()` runs every collector registered in `app/redfish/collectors/__init__.py:COLLECTORS`.
5. Each collector returns a list of `ComponentRow`s plus a `summary` dict. Failures become warnings, not aborts — partial data is more useful than no data.
6. The walker persists a `Server` row plus its `Component`s in a single transaction. The raw Redfish payload is stored in `Server.raw_payload` as JSON for deep dives.
7. After every host transition the runner publishes a `host.start`/`host.progress`/`host.done`/`host.failed` event on `bus["job:{inventory_id}"]`. WebSocket subscribers (the Live progress screen) see them within milliseconds.
8. When the queue drains: `status=complete` if everything succeeded, `complete-warn` if anything raised, `failed` if **nothing** succeeded. The job emits a final `job.done` event and a `TelemetryEvent` is recorded.

## Data flow — Smart Hands

The same envelope flows the *long way around*, with a cryptographic signature chain to keep it honest.

```
operator side                                                       remote side
─────────────                                                       ───────────
POST /smart-hands/generate
  │
  ├─ create Inventory(mode=smart-hands, status=awaiting-results)
  ├─ generate 32-byte seed → store in Inventory.integrity_seed
  ├─ derive ed25519 signing key from seed
  ├─ hash collect.py → expected_script_sha256
  └─ pack tar.gz:
        meta.json                  ← inventory_id, seed, expected_script_sha256
        inventory.csv              ← optional pre-fill
        requirements.txt
        collect.py                 ← standalone entrypoint
        hpersist_collector/
          client.py                ← async Redfish client (mirror)
          collectors.py            ← collectors as async functions (one-file
                                     mirror of app/redfish/collectors/),
                                     registered as (name, fn) tuples — see
                                     docs/EXTENDING.md for the shape
          walker.py                ← collect_host(), with collection-based
                                     discovery and BMC-preferred manager pick
          runner.py                ← reads CSV, walks hosts, prints progress
          integrity.py             ← build_chain(), write_envelope()

                              ─── archive shipped ───►

                                                                 unzip
                                                                 python -m venv .venv
                                                                 pip install -r requirements.txt
                                                                 python collect.py
                                                                   ├─ walk every host in inventory.csv
                                                                   ├─ build per-host hash chain
                                                                   ├─ sign with seed-derived key
                                                                   └─ write results.hpr (tar.gz)

                              ◄─── results.hpr returned ───

POST /smart-hands/process
  │
  ├─ verify envelope structure (.tar.gz with envelope.json)
  ├─ check integrity_seed against any pending Inventory   ── step "Metadata signature"
  ├─ recompute chain from results{} payloads              ── step "Per-host hash chain"
  ├─ compare collector script SHA-256 with meta's value   ── step "Collector script integrity"
  │     ── mismatch is informational, not fatal: tamper_check=script-modified
  ├─ validate schema is hpersist/v1                       ── step "Results schema"
  └─ persist Server + Component rows                      ── step "Persist to local sqlite"
```

### Why hash chain *and* ed25519?

- The **hash chain** detects tampering with the result payloads — any byte flip in any host's data breaks subsequent chain hashes, so the operator sees exactly which host was altered.
- The **ed25519 signatures** prove the chain was built by someone holding the seed (i.e. the same collector archive). They prevent forging a brand-new chain from synthesized data.
- The **collector script SHA-256** is a separate honesty check on the executable — surfaced as a warning, not a blocker, because some sites legitimately patch the script (e.g. for proxies).

## File layout

The data directory defaults to `<project_root>/data/` and is overridable
with `HPERSIST_DATA_DIR=/some/other/path`.

```
data/
├── hpersist.db          # SQLite (WAL mode)
├── hpersist.db-wal      # WAL journal
├── hpersist.db-shm      # shared memory
├── instance.key         # per-instance ed25519 signing key (lazy-created
│                        # by app/core/integrity.py; reserved for signing
│                        # operator-side artifacts, not yet wired in)
├── logs/
│   └── inv-<id>.log     # one per inventory, replayed into the Logs tab
├── archives/
│   └── hpersist-collector-<slug>-<timestamp>.tar.gz
└── uploads/
    └── <whatever-the-engineer-named-it>.hpr
```

## Configuration

All settings are env-driven via pydantic-settings. The prefix is `HPERSIST_`
and `__` separates nested groups (`server`, `db`, `collector`, `log`, `cors`).
Examples:

```
HPERSIST_ENV=prod
HPERSIST_DATA_DIR=/var/lib/hpersist
HPERSIST_SERVER__HOST=0.0.0.0
HPERSIST_SERVER__PORT=8765
HPERSIST_SERVER__LOG_LEVEL=info
HPERSIST_DB__URL=postgresql+psycopg://user:pass@host/hpersist
HPERSIST_DB__POOL_SIZE=20
HPERSIST_DB__SQLITE_BUSY_TIMEOUT_MS=15000
HPERSIST_COLLECTOR__CONCURRENCY=32
HPERSIST_COLLECTOR__TIMEOUT_SECONDS=8
HPERSIST_COLLECTOR__TLS_VERIFY=warn-only      # strict|warn-only|off
HPERSIST_LOG__LEVEL=INFO
HPERSIST_LOG__RETENTION_DAYS=90
HPERSIST_CORS__ALLOW_ORIGINS=["https://hpersist.example.com"]
```

See [`.env.example`](../.env.example) for the full catalogue with defaults.

## Integrity model — state machine

```
                       ┌───────────────────────────────────────────────┐
                       │                                               │
              POST     ▼                          POST                 │
   ┌────────┐ /smart-hands/generate  ┌───────────────────┐ /smart-hands/process
   │ (none) │ ─────────────────────► │ awaiting-results  │ ────────────────────────►
   └────────┘                        └───────────────────┘
                                              │
                                              │ chain valid?  signature valid?  schema valid?
                                              │
                                              ▼
                                   ┌───────────────────────┐         ┌──────────┐
                                   │ complete              │         │ failed   │
                                   │  integrity=ok or      │   ◄─────│  - chain │
                                   │  integrity=script-    │         │  - sig   │
                                   │             modified  │         │  - schema│
                                   └───────────────────────┘         └──────────┘
```

For local collections, the path is `in-progress` → (`complete` | `complete-warn` | `failed`); no integrity stamps because the operator runs the collector themselves.

## Extensibility seams

| What | Where | How |
|------|-------|-----|
| New Redfish collector | `app/redfish/collectors/`, register in `__init__.py:COLLECTORS` | subclass `BaseCollector`, implement `async def collect(self, client, system, chassis, manager) -> CollectorResult`. To also collect remotely, mirror as an async function in `app/smart_hands/template/hpersist_collector/collectors.py` and register as a tuple — the SH walker has a different contract. |
| New tool | `app/tools/<name>.py` + route in `app/api/tools.py` | plain function (or async); expose via APIRouter, then sidebar entry, route case, screen component, locale keys. Full step-by-step in [EXTENDING.md](EXTENDING.md). |
| New locale | `app/locales/<code>.json` | copy `en.json`, translate, keep `_meta` block at the top; UI picks it up via `GET /api/v1/locales` without rebuild. |
| New export format | `app/exports/<format>.py` + branch in `app/api/exports.py` | input is `list[ExportSheet]` (each `rows: list[list]` aligned with `columns`), output is bytes; widen the `format` regex on `ExportRequest`. |
| New database column | `app/models.py` + `python -m alembic revision --autogenerate -m "..."` | `start.bat`/`start.sh` runs `alembic upgrade head` before launching uvicorn, so the migration is applied automatically on the next start. |

The frontend mirrors this: drop a new screen as a function in `frontend/screens/<feature>.jsx`, register the `<script src="screens/<feature>.jsx?v=N">` in `index.html` (the load order is explicit, no bundler), add a route case in `app.jsx`, and bump the `?v=` cache-bust.

## Known limits

- SQLite handles a few hundred inventories with a few thousand servers each comfortably. Past that, swap `db_url` for PostgreSQL — every query is plain SQLAlchemy 2.x, no SQLite-specific SQL.
- The in-process job runner is bounded by `default_concurrency` (default 16). To collect a 5k-server site, raise it to 64 and budget RAM (~80MB at 64 in-flight).
- WebSocket reconnects aren't automatic on the frontend — the progress screen reconnects on remount but a long disconnect mid-job will miss intermediate events. The `Inventory` is the source of truth; refresh the inventory detail to see the final state.
