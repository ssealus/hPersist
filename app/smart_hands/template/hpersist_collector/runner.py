"""Synchronous wrapper that drives the async collector with progress prints."""
from __future__ import annotations

import asyncio
import sys

from .client import RedfishCreds
from .walker import collect_host


def run_collection(hosts: list[dict], *, concurrency: int = 8, timeout: float = 8.0, tls: str = "warn-only") -> list[dict]:
    return asyncio.run(_run_async(hosts, concurrency=concurrency, timeout=timeout, tls=tls))


async def _run_async(hosts: list[dict], *, concurrency: int, timeout: float, tls: str) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = [None] * len(hosts)  # type: ignore[list-item]

    async def worker(idx: int, row: dict) -> None:
        async with sem:
            creds = RedfishCreds(username=row["login"], password=row["password"], tls_verify=tls)
            res = await collect_host(row["ip"], creds, timeout=timeout)
            # carry the CSV hostname into the payload — Redfish HostName is often blank
            if row.get("hostname"):
                res["csv_hostname"] = row["hostname"]
            results[idx] = res
            _print_line(res, row.get("hostname"))

    await asyncio.gather(*(worker(i, h) for i, h in enumerate(hosts)))
    return results


def _print_line(res: dict, hostname: str | None) -> None:
    ip = res["host"].ljust(15)
    name = (hostname or _g(res, "summary", "system", "hostname") or "—").ljust(18)
    gen = _g(res, "summary", "manager", "generation") or "—"
    if res["success"]:
        parts = len(res.get("components") or [])
        print(f"  [ok ] {ip}  {name}  {gen:<6}  {res['duration_seconds']:>5.1f}s · {parts} items", file=sys.stdout, flush=True)
    else:
        print(f"  [err] {ip}  ⟶ {res['error']}", file=sys.stdout, flush=True)


def _g(d: dict, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur
