"""Orchestrator — cache → fetch → parse → cache. No live calls."""
from __future__ import annotations

import pytest

from app.tools.partsurfer import cache, service


async def test_search_empty_query_short_circuits(db_session):
    result = await service.search(db_session, "")
    assert result["not_found"] is True
    assert result["meta"]["source"] == "noop"


async def test_search_cache_hit_skips_upstream(db_session, monkeypatch: pytest.MonkeyPatch):
    cache.put(db_session, "ABC-1", {"product": {"sn": "ABC-1"}, "spare_bom": [], "not_found": False, "hint": ""})
    db_session.commit()

    async def boom(*_, **__):
        raise AssertionError("upstream must not be called when cache is fresh")
    monkeypatch.setattr("app.tools.partsurfer.client.fetch", boom)

    result = await service.search(db_session, "abc-1")  # case normalisation
    assert result["meta"]["cached"] is True
    assert result["meta"]["source"] == "cache"
    assert result["product"] == {"sn": "ABC-1"}


async def test_search_force_refresh_bypasses_cache(db_session, monkeypatch: pytest.MonkeyPatch):
    cache.put(db_session, "USE839N0CK", {"product": {"old": True}, "spare_bom": [], "not_found": False, "hint": ""})
    db_session.commit()

    async def fake_fetch(_q, **__):
        return "<html></html>"
    def fake_parse(_html):
        return {"product": {"new": True}, "spare_bom": [], "not_found": False, "hint": ""}

    monkeypatch.setattr("app.tools.partsurfer.client.fetch", fake_fetch)
    monkeypatch.setattr("app.tools.partsurfer.parser.parse", fake_parse)

    result = await service.search(db_session, "USE839N0CK", force_refresh=True)
    assert result["meta"]["source"] == "live"
    assert result["product"] == {"new": True}


async def test_search_live_path_persists_to_cache(db_session, monkeypatch: pytest.MonkeyPatch):
    async def fake_fetch(_q, **__):
        return "<html></html>"
    def fake_parse(_html):
        return {"product": {"sn": "X"}, "spare_bom": [{"k": "v"}], "not_found": False, "hint": ""}

    monkeypatch.setattr("app.tools.partsurfer.client.fetch", fake_fetch)
    monkeypatch.setattr("app.tools.partsurfer.parser.parse", fake_parse)

    await service.search(db_session, "newkey")
    db_session.commit()

    cached = cache.get_fresh(db_session, "NEWKEY")
    assert cached is not None
    assert cached["product"] == {"sn": "X"}
    assert cached["spare_bom"] == [{"k": "v"}]
