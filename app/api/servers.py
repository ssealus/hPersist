"""Per-server detail and re-poll."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Server

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("/{server_id}")
def get_server(server_id: str, session: Session = Depends(get_session)) -> dict:
    srv = session.get(Server, server_id)
    if srv is None:
        raise HTTPException(404, "server not found")

    components = [
        {
            "id": c.id,
            "group": c.group,
            "label": c.label,
            "part_number": c.part_number,
            "serial_number": c.serial_number,
            "location": c.location,
            "manufacturer": c.manufacturer,
            "quantity": c.quantity,
            "capacity_value": c.capacity_value,
            "capacity_unit": c.capacity_unit,
            "firmware_version": c.firmware_version,
            "health": c.health,
            "extra": c.extra,
        }
        for c in srv.components
    ]
    return {
        "id": srv.id,
        "inventory_id": srv.inventory_id,
        "hostname": srv.hostname,
        "ilo_ip": srv.ilo_ip,
        "serial_number": srv.serial_number,
        "sku": srv.sku,
        "model": srv.model,
        "manufacturer": srv.manufacturer,
        "form_factor": srv.form_factor,
        "generation": srv.generation,
        "ilo_generation": srv.ilo_generation,
        "ilo_firmware": srv.ilo_firmware,
        "bios_version": srv.bios_version,
        "power_state": srv.power_state,
        "health": srv.health,
        "total_memory_gb": srv.total_memory_gb,
        "total_storage_gb": srv.total_storage_gb,
        "collection_status": srv.collection_status,
        "collection_error": srv.collection_error,
        "duration_seconds": srv.duration_seconds,
        "collected_at": srv.collected_at.isoformat(timespec="seconds") if srv.collected_at else None,
        "components": components,
        "components_by_group": _group(components),
        "raw_payload_size": len(str(srv.raw_payload)) if srv.raw_payload else 0,
    }


@router.get("/{server_id}/raw")
def get_server_raw(server_id: str, session: Session = Depends(get_session)) -> dict:
    srv = session.get(Server, server_id)
    if srv is None:
        raise HTTPException(404, "server not found")
    return srv.raw_payload or {}


def _group(components: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for c in components:
        out.setdefault(c["group"], []).append(c)
    return out
