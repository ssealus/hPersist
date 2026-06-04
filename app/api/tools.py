"""Tools endpoints — Redfish tester and PartSurfer lookup.

Firmware compare and BOM diff are deferred to post-MVP; see ``docs/ROADMAP.md``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import RedfishTestRequest
from app.db import get_session
from app.tools.partsurfer import service as partsurfer_service
from app.tools.partsurfer.client import PartSurferError
from app.tools.redfish import tester as redfish_tester

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/redfish-test")
async def redfish_test(req: RedfishTestRequest) -> dict:
    return await redfish_tester.send_request(
        host=req.host,
        method=req.method,
        path=req.path,
        username=req.username,
        password=req.password,
        body=req.body,
        tls=req.tls,
        timeout=req.timeout,
        port=req.port,
    )


@router.get("/redfish-test/history")
def redfish_history() -> list[dict]:
    return redfish_tester.history()


@router.get("/redfish-test/endpoints")
def common_endpoints() -> list[str]:
    return redfish_tester.COMMON_ENDPOINTS


@router.get("/partsurfer/search")
async def partsurfer_search(
    q: str = Query(..., min_length=2, description="Serial number, part number or model"),
    refresh: bool = Query(False, description="Bypass cache, force live fetch"),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return await partsurfer_service.search(session, q, force_refresh=refresh)
    except PartSurferError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
