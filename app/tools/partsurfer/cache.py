"""DB-backed TTL cache for PartSurfer results.

Keys are normalized lookup strings (upper-cased, stripped). Hits bump the
``hits`` counter so we can surface popularity in the UI later. TTL defaults
to 7 days — PartSurfer data is effectively immutable for our use case.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import PartSurferCache

DEFAULT_TTL = timedelta(days=7)


def normalize_key(query: str) -> str:
    return (query or "").strip().upper()


def get_fresh(session: Session, key: str, *, ttl: timedelta = DEFAULT_TTL) -> dict | None:
    """Return cached payload if present AND fresh; bumps hits as a side-effect."""
    row = session.get(PartSurferCache, key)
    if row is None:
        return None
    if datetime.utcnow() - row.fetched_at > ttl:
        return None
    row.hits = (row.hits or 0) + 1
    return row.payload


def put(session: Session, key: str, payload: dict) -> None:
    existing = session.get(PartSurferCache, key)
    if existing is None:
        session.add(PartSurferCache(key=key, fetched_at=datetime.utcnow(), payload=payload, hits=0))
    else:
        existing.fetched_at = datetime.utcnow()
        existing.payload = payload
        existing.hits = 0
