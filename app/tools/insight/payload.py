"""Build a compact per-server table to send to the LLM.

Stays narrow: one row per server with model / SN / status / key components
(CPU, RAM, drives, NICs). No raw Redfish blobs, no credentials.

Anonymizer (opt-in via `llm_anonymize` setting) replaces identifying fields —
SN, hostname, IP, inventory name/organization — with stable per-payload tokens
(`sn-001`, `host-001`, `ip-001`, `inv-1`). Hardware specs (model, generation,
firmware versions, component labels) stay as-is.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.models import Component, Inventory, Server


class _Anonymizer:
    """Map each unique identifying value to a stable short token, per payload."""

    def __init__(self) -> None:
        self._maps: dict[str, dict[str, str]] = {
            "sn": {}, "host": {}, "ip": {}, "inv": {}, "org": {},
        }

    def _tok(self, kind: str, value: str | None) -> str | None:
        if not value or value == "—":
            return value
        m = self._maps[kind]
        if value not in m:
            m[value] = f"{kind}-{len(m) + 1:03d}"
        return m[value]

    def sn(self, v):    return self._tok("sn", v)
    def host(self, v):  return self._tok("host", v)
    def ip(self, v):    return self._tok("ip", v)
    def inv(self, v):   return self._tok("inv", v)
    def org(self, v):   return self._tok("org", v)


def _summarize_components(server: Server) -> dict[str, str]:
    by_group: dict[str, list[Component]] = {}
    for c in server.components:
        by_group.setdefault(c.group, []).append(c)

    out: dict[str, str] = {}
    cpus = by_group.get("CPU", [])
    if cpus:
        labels = Counter(c.label for c in cpus if c.label)
        out["cpu"] = ", ".join(f"{n}× {lbl}" for lbl, n in labels.most_common())

    dimms = by_group.get("DIMM", [])
    if dimms:
        total_gb = sum((c.capacity_value or 0) for c in dimms if c.capacity_unit == "GB")
        labels = Counter(c.label for c in dimms if c.label)
        top_label = labels.most_common(1)[0][0] if labels else ""
        out["ram"] = f"{int(total_gb)} GB ({len(dimms)}× {top_label})" if top_label else f"{int(total_gb)} GB"

    drives = by_group.get("Drive", [])
    if drives:
        total_tb = sum((c.capacity_value or 0) for c in drives if c.capacity_unit == "GB") / 1024
        labels = Counter(c.label for c in drives if c.label)
        top = labels.most_common(1)[0][0] if labels else ""
        out["storage"] = f"{total_tb:.1f} TB ({len(drives)}× {top})" if top else f"{total_tb:.1f} TB"

    nics = by_group.get("NIC", [])
    if nics:
        labels = Counter(c.label for c in nics if c.label)
        out["nic"] = ", ".join(f"{n}× {lbl}" for lbl, n in labels.most_common())

    psus = by_group.get("PSU", [])
    if psus:
        labels = Counter(c.label for c in psus if c.label)
        top = labels.most_common(1)[0][0] if labels else ""
        out["psu"] = f"{len(psus)}× {top}" if top else f"{len(psus)} PSU"

    return out


CONTEXT_LEVELS = ("full", "compact", "summary")


def _row(server: Server, anon: _Anonymizer | None, level: str) -> dict:
    hostname = server.hostname or server.ilo_ip or "—"
    sn = server.serial_number or "—"
    ip = server.ilo_ip or "—"
    if anon:
        hostname = anon.host(hostname)
        sn = anon.sn(sn)
        ip = anon.ip(ip)

    # `compact` drops the per-row component breakdown and a couple of less-load-bearing
    # fields. Saves ~60% of tokens per row while keeping every server identifiable.
    if level == "compact":
        return {
            "hostname": hostname,
            "model": server.model or "—",
            "sn": sn,
            "gen": server.generation or "—",
            "ilo": (server.ilo_generation or "—"),
            "health": server.health or "—",
            "status": server.collection_status or "—",
            "ram_gb": int(server.total_memory_gb) if server.total_memory_gb else None,
            "storage_gb": int(server.total_storage_gb) if server.total_storage_gb else None,
        }

    return {
        "hostname": hostname,
        "ip": ip,
        "model": server.model or "—",
        "sn": sn,
        "gen": server.generation or "—",
        "ilo": f"{server.ilo_generation or ''} {server.ilo_firmware or ''}".strip() or "—",
        "bios": server.bios_version or "—",
        "power": server.power_state or "—",
        "health": server.health or "—",
        "status": server.collection_status or "—",
        "ram_gb": int(server.total_memory_gb) if server.total_memory_gb else None,
        "storage_gb": int(server.total_storage_gb) if server.total_storage_gb else None,
        "components": _summarize_components(server),
    }


def build_payload(
    session: Session,
    inventory_ids: list[str],
    *,
    anonymize: bool = False,
    level: str = "full",
) -> dict:
    """Return a compact dict ready to JSON-serialize into an LLM prompt.

    ``level`` controls how much per-server detail goes to the model:
      - ``full``    — every row with components (cpu/ram/storage/nic/psu summaries)
      - ``compact`` — every row, but without components / bios / ip / power
      - ``summary`` — no per-server rows at all, only aggregate totals
    """
    if level not in CONTEXT_LEVELS:
        raise ValueError(f"unknown context level: {level}")

    invs = (
        session.query(Inventory)
        .filter(Inventory.id.in_(inventory_ids))
        .all()
    )
    if not invs:
        return {"inventories": [], "servers": [], "totals": {}, "anonymized": anonymize, "level": level}

    anon = _Anonymizer() if anonymize else None
    rows: list[dict] = []
    inv_meta: list[dict] = []
    for inv in invs:
        inv_name = anon.inv(inv.name) if anon else inv.name
        inv_org = anon.org(inv.organization) if (anon and inv.organization) else inv.organization
        inv_meta.append({
            "id": inv_name if anon else inv.id,
            "name": inv_name,
            "organization": inv_org,
            "mode": inv.mode,
            "status": inv.status,
            "server_count": len(inv.servers),
        })
        for s in inv.servers:
            row = _row(s, anon, level)
            row["inventory"] = inv_name
            rows.append(row)

    totals = {
        "inventories": len(invs),
        "servers": len(rows),
        "reached": sum(1 for r in rows if r["status"] == "ok"),
        "failed": sum(1 for r in rows if r["status"] == "failed"),
        "models": dict(Counter(r["model"] for r in rows if r["model"] != "—").most_common(10)),
        "generations": dict(Counter(r["gen"] for r in rows if r["gen"] != "—").most_common()),
        "ilo_generations": dict(Counter(r["ilo"].split()[0] for r in rows if r["ilo"] != "—" and r["ilo"].split()).most_common()),
        "health": dict(Counter(r["health"] for r in rows if r["health"] != "—").most_common()),
    }

    # `summary` ships only the aggregate — model gets vendor/gen/health breakdown
    # but no per-server rows. ~80-90% token reduction; loses Q&A about individuals.
    if level == "summary":
        return {
            "inventories": inv_meta,
            "servers_omitted": len(rows),
            "totals": totals,
            "anonymized": anonymize,
            "level": level,
        }

    return {
        "inventories": inv_meta,
        "servers": rows,
        "totals": totals,
        "anonymized": anonymize,
        "level": level,
    }
