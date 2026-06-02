"""Thin OpenAI-compatible chat client (httpx).

Supports both blocking ``chat()`` and a streaming ``chat_stream()`` that yields
incremental ``content`` and ``reasoning_content`` deltas as the upstream produces
them. The streaming variant lets the UI render the model's reasoning on the
background while waiting for the final answer.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx


class LLMConfigError(Exception):
    """Raised when LLM settings (base_url / api_key / model) are missing."""


class LLMHTTPError(Exception):
    """Raised when the upstream LLM returns a non-2xx response."""


async def chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
    temperature: float = 0.2,
) -> dict:
    if not base_url or not api_key or not model:
        raise LLMConfigError("LLM is not configured — set base URL, API key and model in Settings.")

    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(url, headers=headers, json=body)

    if r.status_code >= 400:
        # Pass through provider error body so the UI can show it.
        raise LLMHTTPError(f"upstream {r.status_code}: {r.text[:500]}")

    data = r.json()
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMHTTPError(f"unexpected response shape: {exc}; body={r.text[:300]}") from exc

    content = (message.get("content") or "").strip()
    # Reasoning models (qwen3-thinking, deepseek-r1, …) put internal CoT under
    # `reasoning_content`. If `content` came back empty (usually finish_reason=length
    # — model ran out of budget mid-thought) we surface the reasoning so the UI
    # has SOMETHING to show instead of a blank box.
    reasoning = (message.get("reasoning_content") or "").strip()
    finish_reason = choice.get("finish_reason")

    usage = data.get("usage") or {}
    usage_out = {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
    }

    return {
        "content": content,
        "reasoning": reasoning,
        "finish_reason": finish_reason,
        "model": data.get("model") or model,
        "usage": usage_out,
    }


async def chat_stream(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 300.0,
    temperature: float = 0.2,
) -> AsyncIterator[dict]:
    """Stream chat completion. Yields delta events then a final summary event.

    Events:
      - ``{"type": "reasoning_delta", "text": "..."}`` — slice of internal CoT
      - ``{"type": "content_delta",   "text": "..."}`` — slice of the answer
      - ``{"type": "done", "content": str, "reasoning": str, "finish_reason": str|None,
            "model": str, "usage": {...}}``
    """
    if not base_url or not api_key or not model:
        raise LLMConfigError("LLM is not configured — set base URL, API key and model in Settings.")

    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        # Most OpenAI-compat providers only emit usage in the final chunk when this is set.
        "stream_options": {"include_usage": True},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    content_buf: list[str] = []
    reasoning_buf: list[str] = []
    finish_reason: str | None = None
    usage_out: dict = {}
    model_out = model

    async with httpx.AsyncClient(timeout=timeout) as c:
        async with c.stream("POST", url, headers=headers, json=body) as r:
            if r.status_code >= 400:
                body_bytes = await r.aread()
                raise LLMHTTPError(f"upstream {r.status_code}: {body_bytes[:500].decode('utf-8', 'replace')}")

            async for raw_line in r.aiter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                if chunk.get("model"):
                    model_out = chunk["model"]
                if chunk.get("usage"):
                    u = chunk["usage"]
                    usage_out = {
                        "prompt_tokens": u.get("prompt_tokens"),
                        "completion_tokens": u.get("completion_tokens"),
                        "total_tokens": u.get("total_tokens"),
                        "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                    }

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}

                if (rc := delta.get("reasoning_content")):
                    reasoning_buf.append(rc)
                    yield {"type": "reasoning_delta", "text": rc}
                if (cc := delta.get("content")):
                    content_buf.append(cc)
                    yield {"type": "content_delta", "text": cc}
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

    yield {
        "type": "done",
        "content": "".join(content_buf).strip(),
        "reasoning": "".join(reasoning_buf).strip(),
        "finish_reason": finish_reason,
        "model": model_out,
        "usage": usage_out,
    }


async def ping(*, base_url: str, api_key: str, model: str, timeout: float = 30.0) -> dict:
    """One-shot 'are you alive' call — minimal payload, returns the same shape as chat()."""
    return await chat(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": "You answer with exactly one short word."},
            {"role": "user", "content": "Say 'pong'."},
        ],
        timeout=timeout,
        temperature=0.0,
    )
