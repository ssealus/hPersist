"""LLM client — mock httpx, no live calls."""
from __future__ import annotations

import json

import httpx
import pytest

from app.tools.insight import client


def _mocked(transport: httpx.MockTransport, monkeypatch: pytest.MonkeyPatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw))


# ── Non-streaming chat() ─────────────────────────────────────

async def test_chat_missing_config_raises():
    with pytest.raises(client.LLMConfigError):
        await client.chat(base_url="", api_key="", model="", messages=[])


async def test_chat_returns_content_and_usage(monkeypatch):
    def handler(_req):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "model": "fake-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
    _mocked(httpx.MockTransport(handler), monkeypatch)

    r = await client.chat(base_url="http://x/v1", api_key="k", model="m", messages=[])
    assert r["content"] == "hello"
    assert r["finish_reason"] == "stop"
    assert r["usage"]["total_tokens"] == 15
    assert r["model"] == "fake-model"


async def test_chat_surfaces_reasoning_when_content_is_empty(monkeypatch):
    """Reasoning models like qwen3-thinking return content='' but reasoning_content
    has the chain-of-thought when they hit max_tokens — surface it for the UI."""
    def handler(_req):
        return httpx.Response(200, json={
            "choices": [{
                "message": {"content": "", "reasoning_content": "thinking out loud"},
                "finish_reason": "length",
            }],
            "model": "qwen3",
            "usage": {"completion_tokens_details": {"reasoning_tokens": 2136}},
        })
    _mocked(httpx.MockTransport(handler), monkeypatch)

    r = await client.chat(base_url="http://x/v1", api_key="k", model="m", messages=[])
    assert r["content"] == ""
    assert r["reasoning"] == "thinking out loud"
    assert r["finish_reason"] == "length"
    assert r["usage"]["reasoning_tokens"] == 2136


async def test_chat_raises_on_upstream_error(monkeypatch):
    _mocked(httpx.MockTransport(lambda req: httpx.Response(502, text="bad gateway")), monkeypatch)
    with pytest.raises(client.LLMHTTPError, match="502"):
        await client.chat(base_url="http://x/v1", api_key="k", model="m", messages=[])


async def test_chat_raises_on_unexpected_shape(monkeypatch):
    _mocked(httpx.MockTransport(lambda req: httpx.Response(200, json={"choices": []})), monkeypatch)
    with pytest.raises(client.LLMHTTPError):
        await client.chat(base_url="http://x/v1", api_key="k", model="m", messages=[])


# ── Streaming chat_stream() ──────────────────────────────────

def _sse_chunks(*chunks: dict) -> bytes:
    """Encode a sequence of delta dicts as SSE 'data: {...}\\n\\n' lines."""
    lines = [f"data: {json.dumps(c)}\n\n".encode() for c in chunks]
    lines.append(b"data: [DONE]\n\n")
    return b"".join(lines)


async def test_chat_stream_yields_deltas_then_done(monkeypatch):
    body = _sse_chunks(
        {"choices": [{"delta": {"reasoning_content": "let me "}, "finish_reason": None}]},
        {"choices": [{"delta": {"reasoning_content": "think."}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "## Answer"}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
    )

    def handler(_req):
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    _mocked(httpx.MockTransport(handler), monkeypatch)

    events = []
    async for ev in client.chat_stream(base_url="http://x/v1", api_key="k", model="m", messages=[]):
        events.append(ev)

    types = [ev["type"] for ev in events]
    assert types[:3] == ["reasoning_delta", "reasoning_delta", "content_delta"]
    assert types[-1] == "done"

    done = events[-1]
    assert done["reasoning"] == "let me think."
    assert done["content"] == "## Answer"
    assert done["finish_reason"] == "stop"
    assert done["usage"]["total_tokens"] == 8


async def test_chat_stream_missing_config_raises():
    with pytest.raises(client.LLMConfigError):
        agen = client.chat_stream(base_url="", api_key="", model="", messages=[])
        await agen.__anext__()
