"""Top-level Redfish walker.

One call per host: probe → discover the three roots (System, Chassis,
Manager) via collection enumeration + System.Links → run every registered
collector → return a `HostRecord`. A failing collector becomes a warning,
not a host-wide abort.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.redfish.client import RedfishClient, RedfishCreds, RedfishError
from app.redfish.collectors import COLLECTORS, ComponentRow


@dataclass(slots=True)
class HostRecord:
    host: str
    success: bool
    duration_seconds: float
    error: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    components: list[ComponentRow] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


async def collect_host(
    host: str,
    creds: RedfishCreds,
    *,
    timeout: float = 8.0,
    logger=None,
) -> HostRecord:
    started = time.perf_counter()

    def _log(level: str, msg: str) -> None:
        if logger:
            getattr(logger, level)(msg, host=host)

    try:
        async with RedfishClient(host, creds, timeout=timeout) as client:
            _log("info", "probing Redfish service root")
            probe = await client.probe()
            if not probe.reachable:
                return _failed(host, started, f"unreachable: {probe.error}")
            if not probe.redfish_ok:
                return _failed(host, started, f"redfish denied: {probe.error}")

            _log("info", f"service root ok · {probe.rtt_ms:.0f}ms")

            roots: dict[str, dict] = {}
            try:
                roots["System"] = await _first_member(client, "/redfish/v1/Systems", "System")
            except RedfishError as exc:
                return _failed(host, started, f"System fetch failed: {exc}")
            try:
                roots["Chassis"] = await _pick_linked(
                    client, roots["System"], "Chassis", "/redfish/v1/Chassis"
                )
            except RedfishError as exc:
                return _failed(host, started, f"Chassis fetch failed: {exc}")
            try:
                roots["Manager"] = await _pick_manager(client, roots["System"], "/redfish/v1/Managers")
            except RedfishError as exc:
                return _failed(host, started, f"Manager fetch failed: {exc}")

            summary: dict[str, Any] = {}
            components: list[ComponentRow] = []
            raw_blob: dict[str, Any] = {}
            warnings: list[str] = []
            timings: dict[str, float] = {}

            for collector in COLLECTORS:
                t0 = time.perf_counter()
                try:
                    result = await collector.collect(
                        client,
                        system=roots["System"],
                        chassis=roots["Chassis"],
                        manager=roots["Manager"],
                    )
                except Exception as exc:  # noqa: BLE001
                    msg = f"{collector.name}: {exc.__class__.__name__}: {exc}"
                    warnings.append(msg)
                    _log("warn", msg)
                    continue
                timings[collector.name] = round(time.perf_counter() - t0, 3)
                summary[collector.name] = result.summary
                components.extend(result.components)
                raw_blob.update(result.raw)
                _log("ok", f"{collector.name} · {len(result.components)} item(s) · {timings[collector.name]}s")

            return HostRecord(
                host=host,
                success=True,
                duration_seconds=round(time.perf_counter() - started, 3),
                summary=summary,
                components=components,
                raw=raw_blob,
                warnings=warnings,
                timings=timings,
            )

    except RedfishError as exc:
        return _failed(host, started, str(exc))
    except Exception as exc:  # noqa: BLE001
        return _failed(host, started, f"{exc.__class__.__name__}: {exc}")


def _failed(host: str, started: float, error: str) -> HostRecord:
    return HostRecord(host=host, success=False, duration_seconds=round(time.perf_counter() - started, 3), error=error)


async def _first_member(client: RedfishClient, collection_path: str, label: str) -> dict:
    """Open a Redfish collection and return its first member resource."""
    collection = await client.get(collection_path)
    members = collection.get("Members") or []
    if not members:
        raise RedfishError(f"{label} collection is empty", url=collection_path)
    first = members[0].get("@odata.id") if isinstance(members[0], dict) else None
    if not first:
        raise RedfishError(f"{label} member missing @odata.id", url=collection_path)
    return await client.get(first)


async def _pick_linked(client: RedfishClient, system: dict, links_key: str, fallback_collection: str) -> dict:
    """Follow System.Links[links_key] if present, otherwise grab the first
    collection member. Necessary for multi-chassis boxes (Cray EX) where
    the first /Chassis member is some sibling enclosure, not the compute node.
    """
    refs = ((system.get("Links") or {}).get(links_key)) or []
    for ref in refs if isinstance(refs, list) else []:
        url = ref.get("@odata.id") if isinstance(ref, dict) else None
        if url:
            try:
                return await client.get(url)
            except RedfishError:
                continue
    return await _first_member(client, fallback_collection, links_key)


# lower rank wins. AuxiliaryController boxes (mezzanine PIC, fan board) are
# never what we want — the real BMC is in here somewhere.
_MANAGER_TYPE_RANK = {
    "BMC": 0,
    "ManagementController": 1,
    "EnclosureManager": 2,
    "Service": 3,
}


async def _pick_manager(client: RedfishClient, system: dict, fallback_collection: str) -> dict:
    """System.Links.ManagedBy first, otherwise the best-ranked collection
    member by ManagerType. Needed for Cray EX (MCU0/MCU1 + BMC) and similar.
    """
    refs = ((system.get("Links") or {}).get("ManagedBy")) or []
    for ref in refs if isinstance(refs, list) else []:
        url = ref.get("@odata.id") if isinstance(ref, dict) else None
        if url:
            try:
                return await client.get(url)
            except RedfishError:
                continue

    coll = await client.get(fallback_collection)
    members = coll.get("Members") or []
    if not members:
        raise RedfishError("Manager collection is empty", url=fallback_collection)

    candidates: list[dict] = []
    for m in members:
        url = m.get("@odata.id") if isinstance(m, dict) else None
        if not url:
            continue
        try:
            candidates.append(await client.get(url))
        except RedfishError:
            continue
    if not candidates:
        raise RedfishError("Manager collection has no fetchable members", url=fallback_collection)

    candidates.sort(key=lambda r: _MANAGER_TYPE_RANK.get(r.get("ManagerType") or "", 99))
    return candidates[0]
