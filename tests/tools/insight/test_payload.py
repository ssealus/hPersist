"""Payload builder + anonymizer — pure functions, no IO."""
from __future__ import annotations

from app.models import Component, Inventory, Server
from app.tools.insight.payload import CONTEXT_LEVELS, _Anonymizer, build_payload


def _seed(session, n_servers: int = 2):
    """Build a single inventory with N synthetic servers and one component each."""
    inv = Inventory(
        name="prod-rack-1", organization="Acme", mode="cidr", submode="cidr",
        status="complete",
    )
    session.add(inv)
    session.flush()
    for i in range(n_servers):
        s = Server(
            inventory_id=inv.id,
            hostname=f"host-{i:02d}", ilo_ip=f"10.0.0.{i+1}",
            serial_number=f"SN{i:08d}",
            model="ProLiant DL360 Gen10", manufacturer="HPE",
            generation="Gen10", ilo_generation="iLO 5", ilo_firmware="2.46",
            bios_version="A40 v2.50", power_state="On", health="OK",
            total_memory_gb=64.0, total_storage_gb=960.0,
            collection_status="ok", duration_seconds=2.5,
        )
        session.add(s)
        session.flush()
        session.add(Component(
            server_id=s.id, group="CPU", label="Xeon Gold 6230",
            part_number="P12345", quantity=2,
        ))
        session.add(Component(
            server_id=s.id, group="DIMM", label="16GB DDR4 3200",
            capacity_value=16.0, capacity_unit="GB", quantity=4,
        ))
    session.commit()
    return inv


# ── Anonymizer ────────────────────────────────────────────────

def test_anonymizer_returns_stable_token_per_input():
    a = _Anonymizer()
    assert a.host("iLO-1") == "host-001"
    assert a.host("iLO-1") == "host-001"  # idempotent


def test_anonymizer_assigns_distinct_tokens_to_distinct_inputs():
    a = _Anonymizer()
    assert a.host("alpha") == "host-001"
    assert a.host("beta") == "host-002"
    assert a.host("gamma") == "host-003"


def test_anonymizer_namespaces_are_independent():
    a = _Anonymizer()
    a.host("x")
    assert a.sn("x") == "sn-001"
    assert a.ip("x") == "ip-001"
    assert a.inv("x") == "inv-001"


def test_anonymizer_passes_through_none_and_dash():
    a = _Anonymizer()
    assert a.host(None) is None
    assert a.host("") == ""
    assert a.host("—") == "—"


# ── build_payload core shape ──────────────────────────────────

def test_build_payload_empty_input_returns_empty_shape(db_session):
    p = build_payload(db_session, [])
    assert p["servers"] == []
    assert p["inventories"] == []
    assert p["totals"] == {}


def test_build_payload_full_level_includes_components(db_session):
    inv = _seed(db_session, n_servers=2)
    p = build_payload(db_session, [inv.id], level="full")
    assert len(p["servers"]) == 2
    row = p["servers"][0]
    assert row["model"] == "ProLiant DL360 Gen10"
    assert row["ip"] == "10.0.0.1"
    assert row["bios"] == "A40 v2.50"
    assert "components" in row
    assert row["components"]["cpu"]  # CPU summary present
    assert row["components"]["ram"]  # DIMM summary present


def test_build_payload_compact_level_drops_components_and_extras(db_session):
    inv = _seed(db_session, n_servers=2)
    p = build_payload(db_session, [inv.id], level="compact")
    row = p["servers"][0]
    assert "components" not in row
    assert "bios" not in row
    assert "ip" not in row
    assert "power" not in row
    # but identity + key vitals stay
    assert row["hostname"]
    assert row["model"]
    assert row["health"] == "OK"


def test_build_payload_summary_level_omits_servers_entirely(db_session):
    inv = _seed(db_session, n_servers=3)
    p = build_payload(db_session, [inv.id], level="summary")
    assert "servers" not in p
    assert p["servers_omitted"] == 3
    assert p["totals"]["servers"] == 3


def test_build_payload_unknown_level_raises(db_session):
    inv = _seed(db_session, n_servers=1)
    import pytest
    with pytest.raises(ValueError, match="unknown context level"):
        build_payload(db_session, [inv.id], level="ultra-tight")


# ── Anonymization in build_payload ────────────────────────────

def test_build_payload_anonymized_redacts_identifying_fields(db_session):
    inv = _seed(db_session, n_servers=2)
    p = build_payload(db_session, [inv.id], anonymize=True, level="full")
    row = p["servers"][0]
    assert row["hostname"].startswith("host-")
    assert row["sn"].startswith("sn-")
    assert row["ip"].startswith("ip-")
    # but hardware specs aren't touched
    assert row["model"] == "ProLiant DL360 Gen10"
    assert row["gen"] == "Gen10"
    # inventory name also tokenized
    assert p["inventories"][0]["name"].startswith("inv-")


def test_build_payload_anonymized_keeps_same_token_for_same_value(db_session):
    inv = _seed(db_session, n_servers=2)
    p = build_payload(db_session, [inv.id], anonymize=True, level="full")
    # Each server has its own SN, so two rows must get DISTINCT sn tokens.
    sn_tokens = {row["sn"] for row in p["servers"]}
    assert len(sn_tokens) == 2


def test_build_payload_records_flags(db_session):
    inv = _seed(db_session, n_servers=1)
    p = build_payload(db_session, [inv.id], anonymize=True, level="full")
    assert p["anonymized"] is True
    assert p["level"] == "full"


# ── Totals ────────────────────────────────────────────────────

def test_build_payload_totals_count_servers_and_models(db_session):
    inv = _seed(db_session, n_servers=4)
    p = build_payload(db_session, [inv.id])
    assert p["totals"]["servers"] == 4
    assert p["totals"]["reached"] == 4
    assert p["totals"]["models"] == {"ProLiant DL360 Gen10": 4}


def test_context_levels_constant_exposes_three_known_values():
    assert CONTEXT_LEVELS == ("full", "compact", "summary")
