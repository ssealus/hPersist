"""Network scanner endpoints."""
from __future__ import annotations

import asyncio
import dataclasses
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.network.scanner import expand_cidr, scan_cidr

router = APIRouter(prefix="/network", tags=["network"])


class ScanRequest(BaseModel):
    cidr: str
    concurrency: int = 64
    timeout: float = 1.5
    probe_redfish: bool = True


@router.get("/preview")
async def preview(cidr: str) -> dict:
    try:
        hosts = await expand_cidr(cidr)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"cidr": cidr, "host_count": len(hosts), "first": hosts[:8], "last": hosts[-3:]}


@router.get("/scan")
async def scan(cidr: str, concurrency: int = 64, timeout: float = 1.5, probe_redfish: bool = True) -> StreamingResponse:
    """Server-sent events stream of :class:`ScanHit`."""
    try:
        hosts = await expand_cidr(cidr)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    async def gen():
        yield f"event: meta\ndata: {json.dumps({'total': len(hosts), 'cidr': cidr})}\n\n"
        done = 0
        try:
            async for hit in scan_cidr(cidr, concurrency=concurrency, timeout=timeout, probe_redfish=probe_redfish):
                done += 1
                yield f"event: hit\ndata: {json.dumps(dataclasses.asdict(hit))}\n\n"
                if done % 16 == 0 or done == len(hosts):
                    yield f"event: progress\ndata: {json.dumps({'done': done, 'total': len(hosts)})}\n\n"
        except asyncio.CancelledError:
            return
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
