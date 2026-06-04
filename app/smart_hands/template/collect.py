#!/usr/bin/env python3
"""hPersist Smart Hands collector — runs on the customer's host.

Usage:
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
    pip install -r requirements.txt
    python collect.py            # uses inventory.csv next to this script

This script is self-contained: no network connection to hPersist is needed.
It produces ``results.hpr`` (signed envelope), which you send back to the
hPersist operator.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Windows consoles default to cp1252 and choke on the banner glyphs below.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hpersist_collector.integrity import (  # noqa: E402
    build_chain,
    sha256_file,
    write_envelope,
)
from hpersist_collector.runner import run_collection  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="hPersist Smart Hands collector")
    ap.add_argument("--inventory", default=str(ROOT / "inventory.csv"))
    ap.add_argument("--meta", default=str(ROOT / "meta.json"))
    ap.add_argument("--output", default=str(ROOT / "results.hpr"))
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--tls", default="warn-only", choices=["strict", "warn-only", "off"])
    return ap.parse_args()


_UTF8 = (sys.stdout.encoding or "").lower().startswith("utf")
_BAR_CH = "─" if _UTF8 else "-"
_CHECK = "✔" if _UTF8 else "[OK]"
_DOT = "·" if _UTF8 else "-"


def banner(msg: str) -> None:
    bar = _BAR_CH * max(40, len(msg) + 4)
    print(f"\n{bar}\n  {msg}\n{bar}")


def main() -> int:
    args = parse_args()
    inv_path = Path(args.inventory)
    meta_path = Path(args.meta)
    if not inv_path.exists():
        print(f"error: inventory file not found: {inv_path}", file=sys.stderr)
        print("Fill in inventory.csv (header: ip,hostname,login,password) and re-run.", file=sys.stderr)
        return 2
    if not meta_path.exists():
        print(f"error: meta.json not found: {meta_path}", file=sys.stderr)
        return 2

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    banner(f"hPersist collector {_DOT} {meta.get('name', 'unnamed')}")
    print(f"  organisation : {meta.get('organization', '—')}")
    print(f"  description  : {meta.get('description', '—')}")
    print(f"  generator    : {meta.get('generator_version', '?')}")
    print(f"  seed         : {meta.get('integrity_seed', '?')[:8]}…")

    hosts = _read_inventory(inv_path)
    if not hosts:
        print("error: no usable rows in inventory.csv", file=sys.stderr)
        return 2

    print(f"\nCollecting {len(hosts)} host(s), concurrency={args.concurrency}…\n")

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    records = run_collection(hosts, concurrency=args.concurrency, timeout=args.timeout, tls=args.tls)
    elapsed = round(time.perf_counter() - started, 3)

    chain_input: list[tuple[str, dict]] = []
    payloads: dict[str, dict] = {}
    succeeded = 0
    failed = 0
    for r in records:
        if r["success"]:
            succeeded += 1
        else:
            failed += 1
        payloads[r["host"]] = r
        chain_input.append((r["host"], r))

    seed_hex = meta.get("integrity_seed", "")
    seed = bytes.fromhex(seed_hex) if seed_hex else b"\0" * 32
    chain, head = build_chain(chain_input, seed)
    script_hash = sha256_file(Path(__file__))

    envelope = {
        "schema": "hpersist/v1",
        "generated_at": started_at.isoformat(timespec="seconds"),
        "duration_seconds": elapsed,
        "metadata": meta,
        "host_count": len(records),
        "succeeded": succeeded,
        "failed": failed,
        "integrity": {
            "chain_head": head,
            "script_sha256": script_hash,
            "expected_script_sha256": meta.get("expected_script_sha256"),
            "tamper_check": "ok" if script_hash == meta.get("expected_script_sha256") else "script-modified",
        },
        "chain": [dataclasses.asdict(e) for e in chain],
        "results": payloads,
    }

    out_path = Path(args.output)
    write_envelope(envelope, out_path)
    print(f"\n{_CHECK} wrote {out_path.name} {_DOT} {out_path.stat().st_size / 1024:.1f} KB")
    print(f"  ok={succeeded}  failed={failed}  elapsed={elapsed:.1f}s")
    if envelope["integrity"]["tamper_check"] != "ok":
        print(
            "  note: collect.py SHA-256 differs from the generator's record — "
            "the operator will be notified. The result is still usable."
        )
    print("\nSend this file back to the hPersist operator.")
    return 0


def _read_inventory(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        # skip '#' comment lines
        cleaned = (line for line in fh if not line.lstrip().startswith("#"))
        reader = csv.DictReader(cleaned)
        for r in reader:
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            if not r.get("ip") or not r.get("login") or not r.get("password"):
                continue
            rows.append(r)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
