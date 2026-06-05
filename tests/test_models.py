"""Model-level invariants — cascade behaviour, helper properties."""
from __future__ import annotations

from app.models import Component, Inventory, Server


def test_inventory_cascades_to_servers_and_components(db_session):
    inv = Inventory(name="t", mode="cidr", submode="cidr", status="complete")
    db_session.add(inv)
    db_session.flush()
    s = Server(inventory_id=inv.id, hostname="h", serial_number="SN1", collection_status="ok")
    db_session.add(s)
    db_session.flush()
    db_session.add(Component(server_id=s.id, group="CPU", label="x"))
    db_session.commit()

    assert db_session.query(Server).count() == 1
    assert db_session.query(Component).count() == 1

    db_session.delete(inv)
    db_session.commit()

    assert db_session.query(Server).count() == 0
    assert db_session.query(Component).count() == 0


def test_inventory_reached_and_failed_properties(db_session):
    inv = Inventory(name="t", mode="cidr", submode="cidr", status="complete")
    db_session.add(inv)
    db_session.flush()
    for status, sn in [("ok", "A"), ("ok", "B"), ("failed", "C"), ("warn", "D")]:
        db_session.add(Server(inventory_id=inv.id, serial_number=sn, collection_status=status))
    db_session.commit()

    assert inv.reached == 2
    assert inv.failed == 1


def test_server_serial_number_uniqueness_within_inventory(db_session):
    """Two servers with the same SN in one inventory must conflict."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    inv = Inventory(name="u", mode="cidr", submode="cidr", status="complete")
    db_session.add(inv)
    db_session.flush()
    db_session.add(Server(inventory_id=inv.id, serial_number="DUP", collection_status="ok"))
    db_session.add(Server(inventory_id=inv.id, serial_number="DUP", collection_status="ok"))
    with pytest.raises(IntegrityError):
        db_session.commit()
