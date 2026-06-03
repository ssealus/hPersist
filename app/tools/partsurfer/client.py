"""HTTP transport for PartSurfer queries.

We hit ``https://partsurfer.hpe.com/Search.aspx?searchText=<value>`` directly -
HPE has no public API, just the ASP.NET search page. Be a good citizen:
identify ourselves in User-Agent, keep one request in flight, time-out at 15s,
let the cache layer absorb repeats.
"""
from __future__ import annotations

import httpx

from app import __version__

BASE_URL = "https://partsurfer.hpe.com/Search.aspx"
USER_AGENT = f"hPersist/{__version__} (+https://github.com/anthropics/hpersist)"


class PartSurferError(Exception):
    """Raised when the upstream request fails or returns a non-200."""


async def fetch(query: str, *, timeout: float = 15.0) -> str:
    """Return raw HTML for a given lookup string (SN/PN/model)."""
    if not query or not query.strip():
        raise PartSurferError("empty query")
    params = {"searchText": query.strip()}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.7",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
        r = await c.get(BASE_URL, params=params, headers=headers)
    if r.status_code >= 400:
        raise PartSurferError(f"upstream {r.status_code}")
    return r.text
