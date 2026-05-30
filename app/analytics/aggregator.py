"""Inventory-wide aggregations.

Everything here is pure-Python over the ORM; no business logic in SQL beyond
simple ``SELECT``s. Easy to test, easy to extend.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models import Component, Inventory, Server


def inventory_overview(session: Session, inv: Inventory) -> dict[str, Any]:
    servers = inv.servers
    parts = list(_iter_components(servers))

    total_cores = sum(c.extra.get("cores", 0) or 0 for c in parts if c.group == "CPU")
    total_threads = sum(c.extra.get("threads", 0) or 0 for c in parts if c.group == "CPU")
    total_memory_gb = sum(s.total_memory_gb or 0 for s in servers)
    total_storage_gb = sum(s.total_storage_gb or 0 for s in servers)
    total_psu_watts = sum(c.capacity_value or 0 for c in parts if c.group == "PSU")

    return {
        "id": inv.id,
        "name": inv.name,
        "organization": inv.organization,
        "description": inv.description,
        "mode": inv.mode,
        "submode": inv.submode,
        "status": inv.status,
        "created_at": _iso(inv.created_at),
        "completed_at": _iso(inv.completed_at),
        "duration_seconds": inv.duration_seconds,
        "created_by": inv.created_by,
        "collector_version": inv.collector_version,
        "script_sha256": inv.script_sha256,
        "integrity_status": inv.integrity_status,
        "integrity_notes": inv.integrity_notes,
        "totals": {
            "servers": len(servers),
            "reached": inv.reached,
            "failed": inv.failed,
            "cpu_cores": total_cores,
            "cpu_threads": total_threads,
            "memory_gb": round(total_memory_gb, 2),
            "storage_gb": round(total_storage_gb, 2),
            "psu_rated_watts": int(total_psu_watts),
            "unique_models": len({s.model for s in servers if s.model}),
            "component_count": len(parts),
        },
        "health": {
            "ok": sum(1 for s in servers if (s.health or "").lower() in {"ok", "good"}),
            "warn": sum(1 for s in servers if (s.health or "").lower() in {"warning", "warn"}),
            "err": sum(1 for s in servers if (s.health or "").lower() in {"critical", "err", "fail"}),
            "unknown": sum(1 for s in servers if not s.health),
        },
        "ilo_distribution": dict(Counter((s.ilo_generation or "unknown", s.ilo_firmware or "?") for s in servers).most_common()),
        "model_distribution": dict(Counter(s.model or "unknown" for s in servers).most_common()),
        "memory_configurations": dict(
            Counter(
                f"{round(s.total_memory_gb)} GB"
                for s in servers
                if s.total_memory_gb
            ).most_common()
        ),
    }


def parts_breakdown(session: Session, inv: Inventory) -> list[dict[str, Any]]:
    """Return one row per unique (group, label, part_number) tuple."""
    grouped: dict[tuple, dict] = defaultdict(lambda: {"qty": 0, "servers": set(), "examples": []})

    for s in inv.servers:
        for c in s.components:
            key = (c.group, c.label, c.part_number or "—")
            entry = grouped[key]
            entry["qty"] += c.quantity or 1
            entry["servers"].add(s.hostname or s.ilo_ip)
            if len(entry["examples"]) < 3 and c.serial_number:
                entry["examples"].append(c.serial_number)
            entry["health"] = c.health or entry.get("health")
            entry["capacity_unit"] = c.capacity_unit or entry.get("capacity_unit")
            entry["manufacturer"] = c.manufacturer or entry.get("manufacturer")

    out = []
    for (group, label, pn), v in grouped.items():
        out.append({
            "group": group,
            "label": label,
            "part_number": None if pn == "—" else pn,
            "quantity": v["qty"],
            "servers_touched": len(v["servers"]),
            "manufacturer": v.get("manufacturer"),
            "health": v.get("health"),
            "capacity_unit": v.get("capacity_unit"),
            "example_serials": v["examples"],
        })
    out.sort(key=lambda r: (-r["quantity"], r["group"]))
    return out


def fleet_overview(session: Session) -> dict[str, Any]:
    """Top-level dashboard rollup across every inventory."""
    from sqlalchemy import func, select

    inventories = session.scalars(select(Inventory).order_by(Inventory.created_at.desc())).all()
    servers = session.scalars(select(Server)).all()
    components = session.scalars(select(Component)).all()

    healthy = sum(1 for s in servers if (s.health or "").lower() in {"ok", "good"})
    warn = sum(1 for s in servers if (s.health or "").lower() in {"warning", "warn"})
    err = sum(1 for s in servers if (s.health or "").lower() in {"critical", "err", "fail"})

    by_model = Counter(s.model or "unknown" for s in servers).most_common()
    by_ilo_fw = Counter(f"{s.ilo_generation or '?'} · {s.ilo_firmware or '?'}" for s in servers).most_common()

    mem_buckets = Counter(
        f"{int(round(s.total_memory_gb / 64) * 64)} GB" if s.total_memory_gb else "?"
        for s in servers if s.total_memory_gb
    ).most_common(6)

    avg_duration = (
        session.scalar(select(func.avg(Inventory.duration_seconds)).where(Inventory.duration_seconds.is_not(None)))
        or 0
    )

    recent = [
        {
            "id": i.id, "name": i.name, "org": i.organization, "mode": i.mode, "submode": i.submode,
            "servers": len(i.servers), "reached": i.reached, "failed": i.failed,
            "status": i.status, "created_at": _iso(i.created_at), "duration": i.duration_seconds,
        }
        for i in inventories[:6]
    ]

    return {
        "totals": {
            "servers": len(servers),
            "inventories": len(inventories),
            "components": len(components),
            "avg_collection_seconds": round(avg_duration, 1),
        },
        "health": {"ok": healthy, "warn": warn, "err": err},
        "model_distribution": by_model,
        "ilo_firmware_distribution": by_ilo_fw,
        "memory_configurations": mem_buckets,
        "recent": recent,
    }


def health_checks(session: Session, inv: Inventory) -> dict[str, list[dict]]:
    """Health rollups used by the Inventory · Health tab."""
    servers = inv.servers
    stale_fw = [_health_row(s) for s in servers if (s.ilo_firmware or "").startswith(("1.5", "2.7", "2.5"))]
    expiring = []  # warranty data is not captured here; placeholder for future
    no_redundancy = [_health_row(s) for s in servers if (s.total_memory_gb or 0) > 0 and _psu_count(s) < 2]
    dimm_mismatch = [_health_row(s) for s in servers if _dimm_count(s) % 4 != 0]
    return {
        "firmware_drift": stale_fw,
        "warranty_expiring_90d": expiring,
        "psu_redundancy": no_redundancy,
        "dimm_mismatch": dimm_mismatch,
    }


def _iter_components(servers):
    for s in servers:
        yield from s.components


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt else None


def _psu_count(server: Server) -> int:
    return sum(1 for c in server.components if c.group == "PSU")


def _dimm_count(server: Server) -> int:
    return sum(1 for c in server.components if c.group == "DIMM")


def _health_row(s: Server) -> dict:
    return {
        "id": s.id, "hostname": s.hostname, "ilo_ip": s.ilo_ip, "model": s.model,
        "ilo": s.ilo_generation, "ilo_firmware": s.ilo_firmware, "health": s.health,
    }
