"""Tiny in-process pub/sub used by the WebSocket layer.

One channel per running collection job. Subscribers are bounded async queues;
slow consumers drop frames rather than back-pressuring the collector.
"""
from __future__ import annotations

import asyncio
import collections
from typing import Any


class EventBus:
    def __init__(self, *, history: int = 200) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = {}
        self._history: dict[str, collections.deque] = {}
        self._history_size = history
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        async with self._lock:
            buf = self._history.setdefault(channel, collections.deque(maxlen=self._history_size))
            buf.append(event)
            subs = list(self._subs.get(channel, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subs.setdefault(channel, []).append(q)
            history = list(self._history.get(channel, ()))
        for event in history:
            q.put_nowait(event)
        return q

    async def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._subs.get(channel)
            if subs and q in subs:
                subs.remove(q)


bus = EventBus()
