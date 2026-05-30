"""Ad-hoc Redfish probe — what the "Redfish tester" tool calls."""
from __future__ import annotations

import time

import httpx
from sqlalchemy import desc, select

from app.db import session_scope
from app.models import RedfishProbeHistory
from app.redfish.client import RedfishClient, RedfishCreds, _ssl_context


HISTORY_LIMIT = 50


async def send_request(
    *,
    host: str,
    method: str,
    path: str,
    username: str,
    password: str,
    body: dict | None = None,
    tls: str = "warn-only",
    timeout: float = 8.0,
    port: int = 443,
) -> dict:
    base = f"https://{host}:{port}" if port != 443 else f"https://{host}"
    started = time.perf_counter()

    # what we save in history so the UI can click-to-restore. no password — ever.
    req_snapshot = {
        "host": host,
        "port": port,
        "method": method.upper(),
        "path": path,
        "username": username or "",
        "tls": tls,
        "request_body": body if (body is not None and method.upper() != "GET") else None,
    }

    async with httpx.AsyncClient(base_url=base, timeout=timeout, verify=_ssl_context(tls), follow_redirects=True) as c:
        try:
            r = await c.request(
                method.upper(),
                path,
                auth=(username, password) if username else None,
                json=body,
                headers={"Accept": "application/json"},
            )
            ms = round((time.perf_counter() - started) * 1000, 2)
        except httpx.HTTPError as exc:
            ms = round((time.perf_counter() - started) * 1000, 2)
            _append_history({**req_snapshot, "status": 0, "ms": ms})
            return {**req_snapshot, "status": 0, "ms": ms, "error": str(exc)}

    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:8000]}

    _append_history({**req_snapshot, "status": r.status_code, "ms": ms})
    return {
        **req_snapshot,
        "status": r.status_code,
        "ms": ms,
        "headers": dict(r.headers),
        "body": payload,
        "ok": 200 <= r.status_code < 300,
    }


def _append_history(entry: dict) -> None:
    """Insert one probe row. Assumes caller already stripped the password."""
    with session_scope() as s:
        s.add(RedfishProbeHistory(
            host=entry.get("host") or "",
            port=int(entry.get("port") or 443),
            method=entry.get("method") or "GET",
            path=entry.get("path") or "/",
            username=entry.get("username") or None,
            tls=entry.get("tls") or "warn-only",
            request_body=entry.get("request_body"),
            status=int(entry.get("status") or 0),
            duration_ms=float(entry.get("ms") or 0.0),
        ))
        # SQLite has no DELETE ORDER BY — keep the newest HISTORY_LIMIT, drop the rest
        # via a subselect.
        keep_ids = s.scalars(
            select(RedfishProbeHistory.id)
            .order_by(desc(RedfishProbeHistory.ts), desc(RedfishProbeHistory.id))
            .limit(HISTORY_LIMIT)
        ).all()
        if keep_ids:
            stale = s.scalars(
                select(RedfishProbeHistory.id)
                .where(~RedfishProbeHistory.id.in_(keep_ids))
            ).all()
            if stale:
                from sqlalchemy import delete
                s.execute(delete(RedfishProbeHistory).where(RedfishProbeHistory.id.in_(stale)))


def history() -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(
            select(RedfishProbeHistory)
            .order_by(desc(RedfishProbeHistory.ts), desc(RedfishProbeHistory.id))
            .limit(HISTORY_LIMIT)
        ).all()
        return [{
            "host": r.host,
            "port": r.port,
            "method": r.method,
            "path": r.path,
            "username": r.username,
            "tls": r.tls,
            "request_body": r.request_body,
            "status": r.status,
            "ms": r.duration_ms,
            "ts": r.ts.isoformat(timespec="seconds") if r.ts else None,
        } for r in rows]


COMMON_ENDPOINTS = [
    "/redfish/v1/",
    "/redfish/v1/Systems/1",
    "/redfish/v1/Chassis/1",
    "/redfish/v1/Managers/1",
    "/redfish/v1/Systems/1/Memory",
    "/redfish/v1/Systems/1/Processors",
    "/redfish/v1/Systems/1/Storage",
    "/redfish/v1/Systems/1/EthernetInterfaces",
    "/redfish/v1/Chassis/1/NetworkAdapters",
    "/redfish/v1/Chassis/1/Power",
    "/redfish/v1/Chassis/1/Thermal",
    "/redfish/v1/Chassis/1/PCIeDevices",
]
