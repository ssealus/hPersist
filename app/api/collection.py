"""Start a local collection (CIDR sweep or CSV upload)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.api.schemas import CollectionStart
from app.db import session_scope
from app.jobs.runner import HostSpec, schedule
from app.models import Inventory
from app.network.csv_parser import parse_csv

router = APIRouter(prefix="/collections", tags=["collection"])


@router.post("", status_code=202)
async def start_collection(req: CollectionStart) -> dict:
    hosts: list[HostSpec] = []
    if req.mode == "csv":
        if not req.hosts:
            raise HTTPException(400, "csv mode requires hosts[]")
        for h in req.hosts:
            hosts.append(HostSpec(ip=h.ip, hostname=h.hostname, login=h.login, password=h.password))
    elif req.mode == "cidr":
        if not req.hosts:
            raise HTTPException(400, "cidr mode still needs the selected hosts[]")
        if not (req.default_login and req.default_password):
            raise HTTPException(400, "cidr mode requires default_login + default_password")
        for h in req.hosts:
            hosts.append(HostSpec(
                ip=h.ip,
                hostname=h.hostname,
                login=h.login or req.default_login,
                password=h.password or req.default_password,
            ))

    if not hosts:
        raise HTTPException(400, "no hosts to collect")

    def _create_inventory() -> tuple[str, str, str]:
        with session_scope() as s:
            inv = Inventory(
                name=req.name,
                organization=req.organization,
                description=req.description,
                mode="local",
                submode=req.mode,
                status="in-progress",
                created_by=req.created_by,
            )
            s.add(inv)
            s.flush()
            return inv.id, inv.name, inv.status

    inv_id, inv_name, inv_status = await asyncio.to_thread(_create_inventory)

    await schedule(inv_id, hosts, concurrency=req.concurrency, timeout=req.timeout)

    return {"id": inv_id, "name": inv_name, "status": inv_status, "host_count": len(hosts)}


@router.post("/validate-csv")
def validate_csv(payload: dict) -> dict:
    text = payload.get("text") or ""
    report = parse_csv(text)
    return {
        "summary": report.summary(),
        "rows": [
            {
                "line": r.line, "ip": r.ip, "hostname": r.hostname,
                "status": r.status, "message": r.message,
            }
            for r in report.rows
        ],
    }
