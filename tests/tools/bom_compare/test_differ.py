"""BOM differ — pure logic, 100% in-memory."""
from __future__ import annotations

from app.models import Component, Inventory, Server
from app.tools.bom_compare.differ import diff_inventories, diff_server_components


def _srv(session, inv, sn: str, hostname: str = None, model: str = "DL360"):
    s = Server(
        inventory_id=inv.id, hostname=hostname or sn, serial_number=sn,
        model=model, collection_status="ok",
    )
    session.add(s)
    session.flush()
    return s


def _comp(session, server, group: str, location: str, pn: str,
          label: str = "x", cap: float = None, unit: str = None):
    c = Component(
        server_id=server.id, group=group, location=location,
        part_number=pn, label=label, capacity_value=cap, capacity_unit=unit,
    )
    session.add(c)
    session.flush()
    return c


def _two_inventories(session):
    a = Inventory(name="A", mode="cidr", submode="cidr", status="complete")
    b = Inventory(name="B", mode="cidr", submode="cidr", status="complete")
    session.add_all([a, b])
    session.flush()
    return a, b


# ── Per-server diff ──────────────────────────────────────────

def test_identical_servers_produce_zero_diffs(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    _comp(db_session, sa, "DIMM", "DIMM 1", "865408-B21", cap=32, unit="GB")
    _comp(db_session, sb, "DIMM", "DIMM 1", "865408-B21", cap=32, unit="GB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert d == {"added": [], "removed": [], "replaced": [], "upgraded": []}


def test_added_component(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    _comp(db_session, sb, "DIMM", "DIMM 2", "865408-B21", cap=32, unit="GB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert len(d["added"]) == 1
    assert d["added"][0]["part_number"] == "865408-B21"


def test_removed_component(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    _comp(db_session, sa, "Drive", "Bay 1", "P00444-001", cap=960, unit="GB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert len(d["removed"]) == 1
    assert d["removed"][0]["part_number"] == "P00444-001"


def test_replaced_same_slot_different_pn(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    # same slot, different PN — but same capacity → replaced, NOT upgraded
    _comp(db_session, sa, "Drive", "Bay 1", "P00444-001", cap=960, unit="GB")
    _comp(db_session, sb, "Drive", "Bay 1", "P19905-B21", cap=960, unit="GB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert len(d["replaced"]) == 1
    assert d["replaced"][0]["before"]["part_number"] == "P00444-001"
    assert d["replaced"][0]["after"]["part_number"] == "P19905-B21"
    assert d["upgraded"] == []


def test_upgrade_when_capacity_increases(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    _comp(db_session, sa, "DIMM", "DIMM 1", "865408-B21", cap=32, unit="GB")
    _comp(db_session, sb, "DIMM", "DIMM 1", "P28215-B21", cap=64, unit="GB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert d["replaced"] == []
    assert len(d["upgraded"]) == 1
    assert d["upgraded"][0]["before"]["capacity_value"] == 32
    assert d["upgraded"][0]["after"]["capacity_value"] == 64


def test_capacity_unit_mismatch_does_not_become_upgrade(db_session):
    """Bumping from 32 MB to 32 GB shouldn't masquerade as 'upgrade' — different units."""
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "SN001")
    sb = _srv(db_session, b, "SN001")
    _comp(db_session, sa, "Drive", "Bay 1", "X", cap=500, unit="GB")
    _comp(db_session, sb, "Drive", "Bay 1", "Y", cap=2, unit="TB")
    db_session.commit()

    d = diff_server_components(sa, sb)
    assert d["upgraded"] == []
    assert len(d["replaced"]) == 1


# ── Inventory-level diff ─────────────────────────────────────

def test_servers_only_in_a_and_b_listed(db_session):
    a, b = _two_inventories(db_session)
    _srv(db_session, a, "ONLY-A")
    _srv(db_session, a, "BOTH")
    _srv(db_session, b, "BOTH")
    _srv(db_session, b, "ONLY-B-1")
    _srv(db_session, b, "ONLY-B-2")
    db_session.commit()

    result = diff_inventories(a, b)
    assert result["summary"]["servers_matched"] == 1
    assert result["summary"]["servers_only_in_a"] == 1
    assert result["summary"]["servers_only_in_b"] == 2
    assert {s["serial_number"] for s in result["servers_only_in_a"]} == {"ONLY-A"}
    assert {s["serial_number"] for s in result["servers_only_in_b"]} == {"ONLY-B-1", "ONLY-B-2"}


def test_servers_without_sn_dont_match_into_orphan_counts(db_session):
    a, b = _two_inventories(db_session)
    db_session.add(Server(inventory_id=a.id, hostname="no-sn-a", serial_number=None, collection_status="ok"))
    db_session.add(Server(inventory_id=b.id, hostname="no-sn-b", serial_number=None, collection_status="ok"))
    db_session.commit()

    result = diff_inventories(a, b)
    assert result["summary"]["no_sn_a"] == 1
    assert result["summary"]["no_sn_b"] == 1
    assert result["summary"]["servers_matched"] == 0


def test_unchanged_servers_omitted_from_server_diffs(db_session):
    a, b = _two_inventories(db_session)
    sa = _srv(db_session, a, "STABLE")
    sb = _srv(db_session, b, "STABLE")
    _comp(db_session, sa, "DIMM", "1", "X", cap=32, unit="GB")
    _comp(db_session, sb, "DIMM", "1", "X", cap=32, unit="GB")
    db_session.commit()

    result = diff_inventories(a, b)
    assert result["summary"]["servers_matched"] == 1
    assert result["summary"]["servers_changed"] == 0
    assert result["server_diffs"] == []
