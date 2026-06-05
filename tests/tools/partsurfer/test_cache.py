"""Cache layer — normalization, TTL freshness, hits counter."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import PartSurferCache
from app.tools.partsurfer import cache


def test_normalize_key_strips_and_uppercases():
    assert cache.normalize_key("  abc-123  ") == "ABC-123"
    assert cache.normalize_key("") == ""
    assert cache.normalize_key(None) == ""  # type: ignore[arg-type]


def test_put_then_get_fresh_roundtrip(db_session):
    cache.put(db_session, "ABC-1", {"hello": "world"})
    db_session.commit()
    got = cache.get_fresh(db_session, "ABC-1")
    assert got == {"hello": "world"}


def test_get_fresh_returns_none_for_missing_key(db_session):
    assert cache.get_fresh(db_session, "NOPE") is None


def test_get_fresh_bumps_hits_counter(db_session):
    cache.put(db_session, "K1", {"x": 1})
    db_session.commit()
    cache.get_fresh(db_session, "K1")
    cache.get_fresh(db_session, "K1")
    db_session.commit()
    row = db_session.get(PartSurferCache, "K1")
    assert row.hits == 2


def test_put_overwrites_and_resets_fetched_at(db_session):
    cache.put(db_session, "K2", {"v": 1})
    db_session.commit()
    row = db_session.get(PartSurferCache, "K2")
    old = row.fetched_at

    cache.put(db_session, "K2", {"v": 2})
    db_session.commit()
    row = db_session.get(PartSurferCache, "K2")
    assert row.payload == {"v": 2}
    assert row.fetched_at >= old


def test_get_fresh_treats_old_entries_as_expired(db_session):
    cache.put(db_session, "K3", {"x": 1})
    db_session.commit()
    # Hand-back-date to well past the TTL.
    row = db_session.get(PartSurferCache, "K3")
    row.fetched_at = datetime.utcnow() - timedelta(days=8)
    db_session.commit()

    assert cache.get_fresh(db_session, "K3", ttl=timedelta(days=7)) is None


def test_get_fresh_respects_custom_ttl(db_session):
    cache.put(db_session, "K4", {"x": 1})
    db_session.commit()
    row = db_session.get(PartSurferCache, "K4")
    row.fetched_at = datetime.utcnow() - timedelta(minutes=10)
    db_session.commit()

    assert cache.get_fresh(db_session, "K4", ttl=timedelta(minutes=5)) is None
    assert cache.get_fresh(db_session, "K4", ttl=timedelta(hours=1)) is not None
