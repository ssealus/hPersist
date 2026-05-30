"""Inventory CRUD + analytics rollups."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analytics.aggregator import health_checks, inventory_overview, parts_breakdown
from app.core.logging import export_lines, stream_log_lines
from app.db import get_session
from app.models import Inventory

router = APIRouter(prefix="/inventories", tags=["inventories"])


@router.get("")
def list_inventories(session: Session = Depends(get_session)) -> list[dict]:
    # eager-load servers — `reached`/`failed`/`len(servers)` walk the collection
    rows = session.scalars(
        select(Inventory)
        .options(selectinload(Inventory.servers))
        .order_by(Inventory.created_at.desc())
    ).all()
    return [
        {
            "id": i.id,
            "name": i.name,
            "organization": i.organization,
            "description": i.description,
            "mode": i.mode,
            "submode": i.submode,
            "status": i.status,
            "created_at": i.created_at.isoformat(timespec="seconds") if i.created_at else None,
            "completed_at": i.completed_at.isoformat(timespec="seconds") if i.completed_at else None,
            "duration_seconds": i.duration_seconds,
            "servers": len(i.servers),
            "reached": i.reached,
            "failed": i.failed,
            "integrity_status": i.integrity_status,
        }
        for i in rows
    ]


@router.get("/{inventory_id}")
def get_inventory(inventory_id: str, session: Session = Depends(get_session)) -> dict:
    inv = session.get(Inventory, inventory_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory not found")
    return inventory_overview(session, inv)


@router.get("/{inventory_id}/servers")
def list_servers(inventory_id: str, session: Session = Depends(get_session)) -> list[dict]:
    inv = session.get(Inventory, inventory_id)
    if inv is None:
        raise HTTPException(404, "inventory not found")
    out = []
    for s in inv.servers:
        out.append({
            "id": s.id,
            "hostname": s.hostname,
            "ilo_ip": s.ilo_ip,
            "serial_number": s.serial_number,
            "model": s.model,
            "ilo_generation": s.ilo_generation,
            "ilo_firmware": s.ilo_firmware,
            "bios_version": s.bios_version,
            "form_factor": s.form_factor,
            "generation": s.generation,
            "power_state": s.power_state,
            "health": s.health,
            "total_memory_gb": s.total_memory_gb,
            "total_storage_gb": s.total_storage_gb,
            "collection_status": s.collection_status,
            "duration_seconds": s.duration_seconds,
            "component_count": len(s.components),
        })
    return out


@router.get("/{inventory_id}/parts")
def parts(inventory_id: str, session: Session = Depends(get_session)) -> list[dict]:
    inv = session.get(Inventory, inventory_id)
    if inv is None:
        raise HTTPException(404, "inventory not found")
    return parts_breakdown(session, inv)


@router.get("/{inventory_id}/health")
def health(inventory_id: str, session: Session = Depends(get_session)) -> dict:
    inv = session.get(Inventory, inventory_id)
    if inv is None:
        raise HTTPException(404, "inventory not found")
    return health_checks(session, inv)


@router.get("/{inventory_id}/logs")
def logs(inventory_id: str, format: str = "json"):
    if format == "txt":
        return Response("".join(export_lines(inventory_id)), media_type="text/plain")
    lines = list(stream_log_lines(inventory_id))
    return {"lines": lines[-500:]}


@router.delete("/{inventory_id}", status_code=204)
def delete_inventory(inventory_id: str, session: Session = Depends(get_session)) -> None:
    inv = session.get(Inventory, inventory_id)
    if inv is None:
        return
    session.delete(inv)
