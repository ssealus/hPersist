"""AI Insight routes — analyse selected inventories via OpenAI-compatible LLM."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.tools.insight import service
from app.tools.insight.client import LLMConfigError, LLMHTTPError
from app.tools.insight.prompts import REPORT_CHOICES

router = APIRouter(prefix="/insight", tags=["insight"])


class InsightRunBody(BaseModel):
    inventory_ids: list[str] = Field(..., min_length=1)
    mode: str  # summary | analytics | reports
    question: str | None = None
    template: str | None = None


@router.get("/report-templates")
def report_templates() -> dict:
    return {"templates": REPORT_CHOICES}


@router.post("/test")
async def test(session: Session = Depends(get_session)) -> dict:
    try:
        return await service.test_connection(session)
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc))
    except LLMHTTPError as exc:
        raise HTTPException(502, str(exc))


@router.post("/run")
async def run(body: InsightRunBody, session: Session = Depends(get_session)) -> dict:
    if body.mode not in ("summary", "analytics", "reports"):
        raise HTTPException(400, f"unknown mode: {body.mode}")
    if body.mode == "analytics" and not (body.question or "").strip():
        raise HTTPException(400, "analytics mode requires a question")
    if body.mode == "reports" and body.template not in REPORT_CHOICES:
        raise HTTPException(400, f"reports mode requires a template from {REPORT_CHOICES}")

    try:
        return await service.run(
            session,
            inventory_ids=body.inventory_ids,
            mode=body.mode,
            question=body.question,
            template=body.template,
        )
    except LLMConfigError as exc:
        raise HTTPException(400, str(exc))
    except LLMHTTPError as exc:
        raise HTTPException(502, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _validate(body: InsightRunBody) -> None:
    if body.mode not in ("summary", "analytics", "reports"):
        raise HTTPException(400, f"unknown mode: {body.mode}")
    if body.mode == "analytics" and not (body.question or "").strip():
        raise HTTPException(400, "analytics mode requires a question")
    if body.mode == "reports" and body.template not in REPORT_CHOICES:
        raise HTTPException(400, f"reports mode requires a template from {REPORT_CHOICES}")


@router.post("/run/stream")
async def run_stream(body: InsightRunBody, session: Session = Depends(get_session)):
    _validate(body)

    async def gen():
        try:
            async for ev in service.run_stream(
                session,
                inventory_ids=body.inventory_ids,
                mode=body.mode,
                question=body.question,
                template=body.template,
            ):
                event = ev.pop("type")
                yield f"event: {event}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except LLMConfigError as exc:
            yield f"event: error\ndata: {json.dumps({'status': 400, 'detail': str(exc)})}\n\n"
        except LLMHTTPError as exc:
            yield f"event: error\ndata: {json.dumps({'status': 502, 'detail': str(exc)})}\n\n"
        except ValueError as exc:
            yield f"event: error\ndata: {json.dumps({'status': 400, 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
