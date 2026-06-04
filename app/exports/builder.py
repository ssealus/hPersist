"""Procurement export composer.

Three layouts and four formats (xlsx / xlsm / csv / json). The composer only
*builds* rows — the per-format writers in :mod:`xlsx` and :mod:`csv_writer`
turn the rows into bytes.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Inventory

ALL_GROUPS = ["System", "CPU", "DIMM", "Drive", "Controller", "NIC", "Port", "PCIe", "PSU"]


@dataclass(slots=True)
class ExportOptions:
    layout: str = "flat"            # flat | by_server | by_part
    groups: list[str] = field(default_factory=lambda: list(ALL_GROUPS))
    include_columns: set[str] = field(default_factory=lambda: {"server", "sn", "model", "group", "part", "pn", "qty"})
    anonymize: bool = False
    inventory_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ExportOptions:
        return cls(
            layout=d.get("layout") or "flat",
            groups=d.get("groups") or list(ALL_GROUPS),
            include_columns=set(d.get("include_columns") or {"server", "sn", "model", "group", "part", "pn", "qty"}),
            anonymize=bool(d.get("anonymize")),
            inventory_ids=d.get("inventory_ids") or [],
        )


@dataclass(slots=True)
class ExportSheet:
    name: str
    columns: list[str]
    rows: list[list]


def build_sheets(session: Session, inventories: list[Inventory], options: ExportOptions) -> list[ExportSheet]:
    flat = _flat_rows(inventories, options)

    sheets: list[ExportSheet] = [
        ExportSheet(name="Bill of materials", columns=_bom_cols(), rows=list(_bom_rows(flat))),
        ExportSheet(name="By server", columns=_by_server_cols(options), rows=list(_by_server_rows(flat, options))),
        ExportSheet(name="By part", columns=_by_part_cols(), rows=list(_by_part_rows(flat))),
    ]
    return sheets


def _flat_rows(inventories: list[Inventory], options: ExportOptions) -> list[dict]:
    rows: list[dict] = []
    for inv in inventories:
        for srv_index, server in enumerate(inv.servers):
            for comp in server.components:
                if comp.group not in options.groups:
                    continue
                rows.append({
                    "inventory": inv.name,
                    "server": _anon(server.hostname or server.ilo_ip or f"host-{srv_index+1:03d}", options, kind="host", index=srv_index),
                    "sn": "—" if options.anonymize else (server.serial_number or "—"),
                    "ilo_ip": "—" if options.anonymize else (server.ilo_ip or "—"),
                    "model": server.model or "—",
                    "group": comp.group,
                    "part": comp.label,
                    "pn": comp.part_number or "—",
                    "qty": comp.quantity or 1,
                    "manufacturer": comp.manufacturer or "—",
                    "firmware": comp.firmware_version or "—",
                    "location": comp.location or "—",
                    "capacity": _fmt_cap(comp.capacity_value, comp.capacity_unit),
                    "warranty_end": "—",  # placeholder
                    "comp_sn": "—" if options.anonymize else (comp.serial_number or "—"),
                })
    return rows


def _bom_cols() -> list[str]:
    return ["Group", "Component", "HPE part #", "Qty"]


def _bom_rows(flat: list[dict]) -> Iterable[list]:
    agg: dict[tuple[str, str, str], int] = {}
    for r in flat:
        k = (r["group"], r["part"], r["pn"])
        agg[k] = agg.get(k, 0) + (r["qty"] or 1)
    for (g, p, pn), qty in sorted(agg.items(), key=lambda kv: (-kv[1], kv[0])):
        yield [g, p, pn, qty]


def _by_server_cols(options: ExportOptions) -> list[str]:
    cols = ["Server"]
    if "sn" in options.include_columns:
        cols.append("SN")
    cols += ["Model", "Group", "Component"]
    if "pn" in options.include_columns:
        cols.append("Part #")
    if "qty" in options.include_columns:
        cols.append("Qty")
    cols += ["Firmware", "Location"]
    return cols


def _by_server_rows(flat: list[dict], options: ExportOptions) -> Iterable[list]:
    flat = sorted(flat, key=lambda r: (r["server"], r["group"]))
    for r in flat:
        row = [r["server"]]
        if "sn" in options.include_columns:
            row.append(r["sn"])
        row += [r["model"], r["group"], r["part"]]
        if "pn" in options.include_columns:
            row.append(r["pn"])
        if "qty" in options.include_columns:
            row.append(r["qty"])
        row += [r["firmware"], r["location"]]
        yield row


def _by_part_cols() -> list[str]:
    return ["Group", "Component", "HPE part #", "Total qty", "Servers touched", "Manufacturer"]


def _by_part_rows(flat: list[dict]) -> Iterable[list]:
    agg: dict[tuple, dict] = {}
    for r in flat:
        k = (r["group"], r["part"], r["pn"])
        v = agg.setdefault(k, {"qty": 0, "servers": set(), "mfr": r["manufacturer"]})
        v["qty"] += r["qty"] or 1
        v["servers"].add(r["server"])
    for (g, p, pn), v in sorted(agg.items(), key=lambda kv: (-kv[1]["qty"], kv[0])):
        yield [g, p, pn, v["qty"], len(v["servers"]), v["mfr"] or "—"]


def _fmt_cap(value, unit) -> str:
    if value is None:
        return "—"
    return f"{value:g} {unit or ''}".strip()


def _anon(value: str, options: ExportOptions, *, kind: str, index: int) -> str:
    if not options.anonymize:
        return value
    if kind == "host":
        return f"host-{index+1:03d}"
    return "—"
