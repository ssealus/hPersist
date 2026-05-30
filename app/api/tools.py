"""Tools endpoints — Redfish tester only.

Part lookup, firmware compare and BOM diff are deferred to post-MVP; see
``docs/ROADMAP.md``.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import RedfishTestRequest
from app.tools import redfish_tester

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
