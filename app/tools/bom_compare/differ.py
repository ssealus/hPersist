"""Pure-logic BOM diff. No DB, no IO — easy to unit-test.

Server matching: by ``serial_number`` (canonical). Hostname is unreliable
(renames happen). Servers without an SN are passed through but won't match.

Component matching within a matched server:
  - Each component is keyed by ``(group, location)`` — "what's installed in
    DIMM slot 5, NIC slot 2, …".
  - Empty/missing location falls into a "loose" bag keyed by ``(group, "")``
    — useful for PSUs, system-wide parts where slot isn't tracked.
  - Slots present on both sides:
      * same part_number → unchanged, dropped from the diff
      * different part_number → ``replaced`` (or ``upgraded`` if the new PN
        has strictly higher capacity_value with the same capacity_unit)
  - Slots only on A → ``removed``
  - Slots only on B → ``added``
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class _CompKey:
    group: str
    location: str

    def as_tuple(self) -> tuple[str, str]:
        return self.group, self.location


def _component_dict(c) -> dict:
    """Serialize one component into the JSON the API returns."""
    return {
        "group": c.group,
        "label": c.label,
        "part_number": c.part_number,
        "location": c.location,
        "manufacturer": c.manufacturer,
        "capacity_value": c.capacity_value,
        "capacity_unit": c.capacity_unit,
        "quantity": c.quantity,
    }


def _server_meta(s) -> dict:
    return {
        "id": s.id,
        "hostname": s.hostname,
        "serial_number": s.serial_number,
        "model": s.model,
    }


def _index_by_slot(components: Iterable) -> dict[tuple[str, str], list]:
    """Bucket components by (group, location). Allows >1 entry per slot for the
    loose '' case (PSUs in two slots with no `location` set, for example)."""
    out: dict[tuple[str, str], list] = defaultdict(list)
    for c in components:
        out[(c.group, c.location or "")].append(c)
    return out


def _is_upgrade(before, after) -> bool:
    """Capacity bump on the same slot — call it an upgrade (worth flagging
    separately from a like-for-like replacement)."""
    if not before.capacity_value or not after.capacity_value:
        return False
    if (before.capacity_unit or "") != (after.capacity_unit or ""):
        return False
    return after.capacity_value > before.capacity_value


def diff_server_components(server_a, server_b) -> dict[str, list]:
    """Diff two server objects' component lists. Both sides must be ORM rows
    so we can read ``components``, ``group``, ``location``, ``part_number``, …
    """
    a_slots = _index_by_slot(server_a.components)
    b_slots = _index_by_slot(server_b.components)

    added: list[dict] = []
    removed: list[dict] = []
    replaced: list[dict] = []
    upgraded: list[dict] = []

    all_slots = set(a_slots) | set(b_slots)
    for slot in all_slots:
        a_items = a_slots.get(slot, [])
        b_items = b_slots.get(slot, [])

        # Walk pairwise by index (after sorting by PN so the result is stable).
        a_items = sorted(a_items, key=lambda c: c.part_number or "")
        b_items = sorted(b_items, key=lambda c: c.part_number or "")
        n = max(len(a_items), len(b_items))
        for i in range(n):
            ca = a_items[i] if i < len(a_items) else None
            cb = b_items[i] if i < len(b_items) else None
            if ca and cb:
                if (ca.part_number or "") == (cb.part_number or "") \
                   and (ca.capacity_value or 0) == (cb.capacity_value or 0):
                    continue  # truly identical
                if (ca.part_number or "") != (cb.part_number or ""):
                    if _is_upgrade(ca, cb):
                        upgraded.append({"before": _component_dict(ca), "after": _component_dict(cb)})
                    else:
                        replaced.append({"before": _component_dict(ca), "after": _component_dict(cb)})
                # Same PN but capacity differs — also an upgrade if value went up.
                elif _is_upgrade(ca, cb):
                    upgraded.append({"before": _component_dict(ca), "after": _component_dict(cb)})
            elif ca:
                removed.append(_component_dict(ca))
            elif cb:
                added.append(_component_dict(cb))

    return {"added": added, "removed": removed, "replaced": replaced, "upgraded": upgraded}


def diff_inventories(inventory_a, inventory_b) -> dict:
    """Top-level diff.

    Match servers by serial_number. Servers with no SN are listed as orphans
    on whichever side they appear.
    """
    a_by_sn = {s.serial_number: s for s in inventory_a.servers if s.serial_number}
    b_by_sn = {s.serial_number: s for s in inventory_b.servers if s.serial_number}
    a_orphans = [s for s in inventory_a.servers if not s.serial_number]
    b_orphans = [s for s in inventory_b.servers if not s.serial_number]

    matched_sns = sorted(set(a_by_sn) & set(b_by_sn))
    only_a = sorted(set(a_by_sn) - set(b_by_sn))
    only_b = sorted(set(b_by_sn) - set(a_by_sn))

    server_diffs: list[dict] = []
    totals = {"added": 0, "removed": 0, "replaced": 0, "upgraded": 0}
    for sn in matched_sns:
        sa, sb = a_by_sn[sn], b_by_sn[sn]
        d = diff_server_components(sa, sb)
        # Only surface servers that actually changed.
        if any(d.values()):
            server_diffs.append({
                "hostname": sa.hostname or sb.hostname,
                "serial_number": sn,
                "model": sa.model or sb.model,
                **d,
            })
        for k in totals:
            totals[k] += len(d[k])

    return {
        "inventory_a": {
            "id": inventory_a.id, "name": inventory_a.name,
            "organization": inventory_a.organization,
            "servers": len(inventory_a.servers),
        },
        "inventory_b": {
            "id": inventory_b.id, "name": inventory_b.name,
            "organization": inventory_b.organization,
            "servers": len(inventory_b.servers),
        },
        "summary": {
            "servers_matched": len(matched_sns),
            "servers_only_in_a": len(only_a),
            "servers_only_in_b": len(only_b),
            "servers_changed": len(server_diffs),
            "no_sn_a": len(a_orphans),
            "no_sn_b": len(b_orphans),
            **totals,
        },
        "server_diffs": server_diffs,
        "servers_only_in_a": [_server_meta(a_by_sn[sn]) for sn in only_a],
        "servers_only_in_b": [_server_meta(b_by_sn[sn]) for sn in only_b],
    }
