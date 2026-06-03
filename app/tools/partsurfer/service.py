"""PartSurfer orchestrator — cache → fetch → parse → cache → return."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.tools.partsurfer import cache, client, parser


async def search(session: Session, query: str, *, force_refresh: bool = False) -> dict:
    """Look up a single SN/PN/model. Adds a `meta` section with cache info."""
    key = cache.normalize_key(query)
    if not key:
        return {
            "query": query,
            "product": {},
            "spare_bom": [],
            "not_found": True,
            "hint": "empty query",
            "meta": {"cached": False, "fetched_at": None, "source": "noop"},
        }

    if not force_refresh:
        hit = cache.get_fresh(session, key)
        if hit is not None:
            return {
                **hit,
                "meta": {
                    "cached": True,
                    "fetched_at": _fetched_at(session, key),
                    "source": "cache",
                },
            }

    html = await client.fetch(key)
    parsed = parser.parse(html)
    payload = {"query": key, **parsed}
    cache.put(session, key, payload)

    return {
        **payload,
        "meta": {
            "cached": False,
            "fetched_at": datetime.utcnow().isoformat(timespec="seconds"),
            "source": "live",
        },
    }


def _fetched_at(session: Session, key: str) -> str | None:
    from app.models import PartSurferCache
    row = session.get(PartSurferCache, key)
    return row.fetched_at.isoformat(timespec="seconds") if row else None
