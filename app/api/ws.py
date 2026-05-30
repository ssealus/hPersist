"""WebSocket endpoint streaming live collection progress."""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.jobs.bus import bus

router = APIRouter(tags=["ws"])


@router.websocket("/ws/jobs/{inventory_id}")
async def job_socket(websocket: WebSocket, inventory_id: str) -> None:
    await websocket.accept()
    channel = f"job:{inventory_id}"
    queue = await bus.subscribe(channel)
    try:
        while True:
            event = await queue.get()
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        await bus.unsubscribe(channel, queue)
