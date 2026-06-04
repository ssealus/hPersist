"""Insight service — settings → payload → llm. No live calls."""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.models import Inventory, Server, UserSetting
from app.tools.insight import service


def _seed_minimal(session):
    inv = Inventory(name="A", mode="cidr", submode="cidr", status="complete")
    session.add(inv)
    session.flush()
    session.add(Server(
        inventory_id=inv.id, hostname="h-01", serial_number="SN001",
        model="DL360", health="OK", collection_status="ok",
    ))
    session.commit()
    return inv


def _set(session, key: str, value: str):
    session.merge(UserSetting(key=key, value=value))
    session.commit()


async def test_run_no_servers_returns_polite_message(db_session, monkeypatch):
    inv = Inventory(name="empty", mode="cidr", submode="cidr", status="awaiting-results")
    db_session.add(inv)
    db_session.commit()

    async def boom(*_, **__):
        raise AssertionError("client must not be called when there are no servers")
    monkeypatch.setattr("app.tools.insight.client.chat", boom)

    r = await service.run(db_session, inventory_ids=[inv.id], mode="summary")
    assert "No servers" in r["answer"]
    assert r["usage"] == {}


async def test_run_reads_anonymize_and_level_from_settings(db_session, monkeypatch):
    inv = _seed_minimal(db_session)
    _set(db_session, "llm_base_url", "http://fake/v1")
    _set(db_session, "llm_api_key", "k")
    _set(db_session, "llm_model", "m")
    _set(db_session, "llm_anonymize", "true")
    _set(db_session, "llm_context_level", "compact")

    captured: dict = {}

    async def fake_chat(*, messages, **__):
        captured["messages"] = messages
        return {"content": "ok", "reasoning": "", "finish_reason": "stop",
                "model": "m", "usage": {"total_tokens": 7}}
    monkeypatch.setattr("app.tools.insight.client.chat", fake_chat)

    r = await service.run(db_session, inventory_ids=[inv.id], mode="summary")
    assert r["anonymized"] is True
    assert r["level"] == "compact"
    # Anonymized payload should NOT contain the real hostname/SN.
    user_msg = captured["messages"][1]["content"]
    assert "h-01" not in user_msg
    assert "SN001" not in user_msg


async def test_run_stream_emits_deltas_then_enriched_done(db_session, monkeypatch):
    inv = _seed_minimal(db_session)
    _set(db_session, "llm_base_url", "http://fake/v1")
    _set(db_session, "llm_api_key", "k")
    _set(db_session, "llm_model", "m")

    async def fake_stream(**_) -> AsyncIterator[dict]:
        yield {"type": "reasoning_delta", "text": "hm"}
        yield {"type": "content_delta", "text": "## Out"}
        yield {"type": "done", "content": "## Out", "reasoning": "hm",
               "finish_reason": "stop", "model": "m", "usage": {"total_tokens": 4}}
    monkeypatch.setattr("app.tools.insight.client.chat_stream", fake_stream)

    events = []
    async for ev in service.run_stream(db_session, inventory_ids=[inv.id], mode="summary"):
        events.append(ev)

    assert [e["type"] for e in events] == ["reasoning_delta", "content_delta", "done"]
    done = events[-1]
    assert done["answer"] == "## Out"
    assert done["reasoning"] == "hm"
    assert done["finish_reason"] == "stop"
    assert "payload_summary" in done
    assert done["anonymized"] is False
    assert done["level"] == "full"


async def test_test_connection_pings_with_settings(db_session, monkeypatch):
    _set(db_session, "llm_base_url", "http://fake/v1")
    _set(db_session, "llm_api_key", "k")
    _set(db_session, "llm_model", "m")

    async def fake_ping(*, base_url, api_key, model, **__):
        assert base_url == "http://fake/v1"
        return {"content": "pong", "model": model, "usage": {}}
    monkeypatch.setattr("app.tools.insight.client.ping", fake_ping)

    r = await service.test_connection(db_session)
    assert r["ok"] is True
    assert r["reply"].startswith("pong")
