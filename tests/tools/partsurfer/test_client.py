"""HTTP client — mock httpx, no live calls."""
from __future__ import annotations

import httpx
import pytest

from app.tools.partsurfer import client


async def test_fetch_rejects_empty_query():
    with pytest.raises(client.PartSurferError, match="empty query"):
        await client.fetch("")
    with pytest.raises(client.PartSurferError):
        await client.fetch("   ")


async def test_fetch_returns_body_on_2xx(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, text="<html>ok</html>")

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw))

    body = await client.fetch("USE839N0CK")
    assert body == "<html>ok</html>"
    assert "searchText=USE839N0CK" in seen["url"]
    assert seen["user_agent"].startswith("hPersist/")


async def test_fetch_raises_on_5xx(monkeypatch: pytest.MonkeyPatch):
    transport = httpx.MockTransport(lambda req: httpx.Response(503, text="busy"))
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw))

    with pytest.raises(client.PartSurferError, match="upstream 503"):
        await client.fetch("X")
