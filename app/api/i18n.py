"""Locale routes — list available languages and fetch a translation pack."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/locales", tags=["i18n"])

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

_LOCALE_CODE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


@router.get("")
def list_locales() -> dict:
    locales = []
    for p in sorted(LOCALES_DIR.glob("*.json")):
        try:
            meta = json.loads(p.read_text(encoding="utf-8")).get("_meta", {})
        except Exception:
            meta = {}
        locales.append({
            "code": p.stem,
            "name": meta.get("name", p.stem),
            "native": meta.get("native", p.stem),
        })
    return {"default": "en", "locales": locales}


@router.get("/{code}")
def fetch_locale(code: str) -> dict:
    if not _LOCALE_CODE.match(code):
        raise HTTPException(404, f"locale {code} not found")
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        raise HTTPException(404, f"locale {code} not found")
    return json.loads(path.read_text(encoding="utf-8"))
