"""Smart Hands endpoints: generate archive, upload + process results."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import SmartHandsGenerate
from app.config import settings
from app.db import get_session
from app.models import Inventory
from app.smart_hands.generator import generate_archive
from app.smart_hands.processor import process_envelope

router = APIRouter(prefix="/smart-hands", tags=["smart-hands"])


@router.post("/generate")
def generate(req: SmartHandsGenerate, session: Session = Depends(get_session)) -> dict:
    # create inventory first so meta.json can embed its id alongside the seed
    inv = Inventory(
        name=req.name,
        organization=req.organization,
        description=req.description,
        mode="smart-hands",
        submode="script",
        status="awaiting-results",
        created_by=req.created_by,
    )
    session.add(inv)
    session.flush()

    archive = generate_archive(
        inventory_name=req.name,
        organization=req.organization,
        description=req.description,
        created_by=req.created_by,
        csv_text=req.csv_text,
        inventory_id=inv.id,
    )

    inv.integrity_seed = archive.seed
    inv.script_sha256 = archive.expected_script_sha256
    session.flush()

    return {
        "inventory_id": inv.id,
        "archive": archive.path.name,
        "download_url": f"/api/v1/smart-hands/download/{archive.path.name}",
        "size_bytes": archive.size_bytes,
        "sha256": archive.sha256,
        "expected_script_sha256": archive.expected_script_sha256,
        "files": archive.file_list,
    }


@router.get("/download/{filename}")
def download(filename: str) -> FileResponse:
    # Basic anti-traversal: must live inside the archives dir.
    archives_dir = settings.data_dir / "archives"
    target = (archives_dir / filename).resolve()
    if not str(target).startswith(str(archives_dir.resolve())) or not target.exists():
        raise HTTPException(404, "archive not found")
    return FileResponse(target, media_type="application/gzip", filename=filename)


@router.post("/process")
async def process(file: UploadFile = File(...)) -> dict:
    uploads_dir = settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dst = uploads_dir / (file.filename or "envelope.hpr")
    with dst.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    # uploaded envelope stays on disk for audit
    report = process_envelope(dst)
    return report.to_dict()
