"""Stats endpoints — fleet rollup and anonymized telemetry export."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.analytics.aggregator import fleet_overview
from app.db import get_session
from app.stats.telemetry import anonymized_export, rollup, storage_footprint

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/fleet")
def fleet(session: Session = Depends(get_session)) -> dict:
    return fleet_overview(session)


@router.get("/rollup")
def rollup_route(window_days: int = 30, session: Session = Depends(get_session)) -> dict:
    return {
        "telemetry": rollup(session, window_days=window_days),
        "storage": storage_footprint(session),
    }


@router.get("/export")
def export_anon(window_days: int = 30, session: Session = Depends(get_session)) -> Response:
    body = anonymized_export(session, window_days=window_days)
    return Response(
        content=json.dumps(body, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="hpersist-telemetry-anon.json"'},
    )
