"""AI Insight routes — analyse selected inventories via OpenAI-compatible LLM."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.tools.insight import service
from app.tools.insight.client import LLMConfigError, LLMHTTPError
from app.tools.insight.prompts import REPORT_CHOICES

logger = logging.getLogger(__name__)

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
        raise HTTPException(400, str(exc)) from exc
    except LLMHTTPError as exc:
        raise HTTPException(502, str(exc)) from exc


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
        raise HTTPException(400, str(exc)) from exc
    except LLMHTTPError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


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
        # Error events surface a curated `detail` string, never the raw exception:
        # LLMHTTPError's message embeds the upstream response body, which can
        # contain provider-side internals or secrets. We log the full text for
        # debugging and ship a generic hint to the client (CodeQL py/stack-trace-exposure).
        except LLMConfigError:
            logger.warning("insight stream: LLM not configured")
            yield f"event: error\ndata: {json.dumps({'status': 400, 'detail': 'LLM is not configured — set base URL, API key and model in Settings.'})}\n\n"
        except LLMHTTPError as exc:
            logger.warning("insight stream: upstream LLM error: %s", exc)
            yield f"event: error\ndata: {json.dumps({'status': 502, 'detail': 'Upstream LLM error — see server logs.'})}\n\n"
        except ValueError as exc:
            logger.warning("insight stream: invalid request: %s", exc)
            yield f"event: error\ndata: {json.dumps({'status': 400, 'detail': 'Invalid request — check mode/question/template.'})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
