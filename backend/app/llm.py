"""The only module that talks to the LLM. Every call returns validated JSON."""
import json
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMRateLimited(LLMError):
    pass


def _retry_after(value: str | None, default: float) -> float:
    try:
        return min(float(value), 20.0) if value else default
    except ValueError:
        return default


def _chat(messages: list[dict], model: str | None, temperature: float, max_tokens: int) -> str:
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY is not set on the server.")
    model = model or settings.llm_model
    if not model:
        raise LLMError("LLM_MODEL is not set on the server.")
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    r = None
    for attempt in range(4):
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=60)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the LLM provider: {exc}") from exc
        if r.status_code == 429:
            if attempt < 3:
                time.sleep(_retry_after(r.headers.get("retry-after"), 2.0 * (attempt + 1)))
                continue
            raise LLMRateLimited("The LLM provider is rate limiting requests (free-tier limit). Try again later.")
        break
    assert r is not None
    if r.status_code >= 400:
        raise LLMError(f"LLM provider returned {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError("Unexpected response shape from the LLM provider.") from exc


def extract_json(text: str) -> dict:
    """Pull one JSON object out of a model reply, tolerating code fences, <think> blocks and chatter."""
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the reply")
    return json.loads(t[start : end + 1])


def complete_json(
    system: str,
    user: str,
    schema: type[T],
    *,
    model: str | None = None,
    retries: int = 1,
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> T:
    """Ask for JSON matching `schema`. On invalid output, feed the error back once and retry."""
    shape = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    messages = [
        {"role": "system", "content": f"{system}\n\nReply with exactly one JSON object matching this JSON schema. No prose, no code fences.\n{shape}"},
        {"role": "user", "content": user},
    ]
    last_error = "unknown"
    for _ in range(retries + 1):
        text = _chat(messages, model, temperature, max_tokens)
        try:
            return schema.model_validate(extract_json(text))
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)[:400]
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That reply was not valid: {last_error}\nReply again with only the corrected JSON object."},
            ]
    raise LLMError(f"The model did not return valid JSON: {last_error}")
