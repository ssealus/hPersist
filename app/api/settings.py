"""User preference store — thin key/value table backed by SQLite."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import UserSetting

router = APIRouter(prefix="/settings", tags=["settings"])

_ALLOWED = {
    "locale", "theme", "density", "direction", "accent",
    "llm_base_url", "llm_api_key", "llm_model", "llm_anonymize", "llm_context_level",
}


@router.get("")
def get_settings(session: Session = Depends(get_session)) -> dict:
    return {r.key: r.value for r in session.query(UserSetting).all()}


@router.patch("")
def patch_settings(body: dict[str, Any], session: Session = Depends(get_session)) -> dict:
    for key, val in body.items():
        if key not in _ALLOWED:
            continue
        existing = session.get(UserSetting, key)
        if existing:
            existing.value = str(val)
        else:
            session.add(UserSetting(key=key, value=str(val)))
    return {"ok": True}
