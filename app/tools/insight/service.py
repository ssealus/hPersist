"""Orchestrator: load settings, build payload, call LLM, return rendered answer."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.tools.insight import client as llm_client
from app.tools.insight.payload import CONTEXT_LEVELS, build_payload
from app.tools.insight.prompts import build_messages
from app.models import UserSetting


def _load_llm_settings(session: Session) -> tuple[str, str, str, bool, str]:
    rows = {r.key: r.value for r in session.query(UserSetting).all()}
    level = rows.get("llm_context_level", "full").strip().lower()
    if level not in CONTEXT_LEVELS:
        level = "full"
    return (
        rows.get("llm_base_url", "").strip(),
        rows.get("llm_api_key", "").strip(),
        rows.get("llm_model", "").strip(),
        rows.get("llm_anonymize", "false").strip().lower() == "true",
        level,
    )


async def run(
    session: Session,
    *,
    inventory_ids: list[str],
    mode: str,
    question: str | None = None,
    template: str | None = None,
) -> dict:
    base_url, api_key, model, anonymize, level = _load_llm_settings(session)

    payload = build_payload(session, inventory_ids, anonymize=anonymize, level=level)
    # `summary` level drops per-server rows entirely. Check totals instead so we
    # still gate on "did we find anything".
    if not payload.get("servers") and not payload.get("servers_omitted"):
        return {
            "answer": "No servers found in the selected inventories.",
            "payload_summary": payload["totals"],
            "usage": {},
            "model": None,
            "anonymized": anonymize,
            "level": level,
        }

    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    messages = build_messages(mode, payload_json=payload_json, question=question, template=template)

    result = await llm_client.chat(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
    )

    return {
        "answer": result["content"],
        "reasoning": result.get("reasoning") or "",
        "finish_reason": result.get("finish_reason"),
        "payload_summary": payload["totals"],
        "usage": result["usage"],
        "model": result["model"],
        "anonymized": anonymize,
        "level": level,
    }


async def run_stream(
    session: Session,
    *,
    inventory_ids: list[str],
    mode: str,
    question: str | None = None,
    template: str | None = None,
):
    """Streaming counterpart of run(). Yields delta dicts then a final dict.

    Same event shape as ``client.chat_stream`` except the terminal "done" event
    is enriched with ``answer``, ``payload_summary``, ``anonymized`` and ``level``
    so the frontend has everything it needs in one packet.
    """
    base_url, api_key, model, anonymize, level = _load_llm_settings(session)
    payload = build_payload(session, inventory_ids, anonymize=anonymize, level=level)

    if not payload.get("servers") and not payload.get("servers_omitted"):
        yield {
            "type": "done",
            "answer": "No servers found in the selected inventories.",
            "reasoning": "",
            "finish_reason": None,
            "payload_summary": payload["totals"],
            "usage": {},
            "model": None,
            "anonymized": anonymize,
            "level": level,
        }
        return

    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    messages = build_messages(mode, payload_json=payload_json, question=question, template=template)

    async for ev in llm_client.chat_stream(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
    ):
        if ev["type"] == "done":
            yield {
                "type": "done",
                "answer": ev["content"],
                "reasoning": ev["reasoning"],
                "finish_reason": ev["finish_reason"],
                "payload_summary": payload["totals"],
                "usage": ev["usage"],
                "model": ev["model"],
                "anonymized": anonymize,
                "level": level,
            }
        else:
            yield ev


async def test_connection(session: Session) -> dict:
    base_url, api_key, model, _, _ = _load_llm_settings(session)
    result = await llm_client.ping(base_url=base_url, api_key=api_key, model=model)
    return {"ok": True, "model": result["model"], "reply": result["content"][:200]}
