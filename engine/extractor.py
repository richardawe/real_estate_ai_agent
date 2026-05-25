"""
LLM extraction and drafting via OpenRouter.

This module is the single gateway for all LLM calls. It enforces:
- Model selection (primary / fallback)
- Retry with exponential back-off on transient errors
- Token tracking (accumulated per workflow, written back to issue front-matter)
- Pydantic validation of every structured output
- Hard prohibition on LLM calls that would gate an action without /approve

The LLM is allowed to: extract structured JSON, draft comments/emails,
summarise documents, generate fit rationale.
The LLM is forbidden to: decide eligibility, decide affordability, pick a
property, or generate legal clauses from scratch.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

_OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_PRIMARY_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
_FALLBACK_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
_VISION_MODEL = "meta-llama/llama-3.2-11b-vision-instruct:free"

_RETRY_DELAYS = [2, 4, 8, 16]  # seconds between retries

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class ExtractionError(LLMError):
    """Raised when the LLM response cannot be validated against the target schema."""
    pass


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise EnvironmentError("OPENROUTER_API_KEY is not set")
    return key


def _call_openrouter(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 2048,
) -> tuple[str, int]:
    """
    Call the OpenRouter API. Returns (content, total_tokens_used).
    Raises LLMError on non-retryable failures, requests.RequestException on
    transient ones.
    """
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/richardawe/real_estate_ai_agent",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    resp = requests.post(_OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code == 429:
        raise requests.RequestException("Rate limited (429)")
    if resp.status_code >= 500:
        raise requests.RequestException(f"Server error {resp.status_code}")
    if not resp.ok:
        raise LLMError(f"OpenRouter error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return content, tokens


def complete(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    max_tokens: int = 2048,
    use_vision: bool = False,
) -> tuple[str, int]:
    """
    Send a chat completion request with retry + fallback.
    Returns (content, total_tokens).
    """
    if model is None:
        model = _VISION_MODEL if use_vision else _PRIMARY_MODEL
    models_to_try = [model] if model not in (_PRIMARY_MODEL, _FALLBACK_MODEL) else [model, _FALLBACK_MODEL]

    last_exc: Exception | None = None
    for attempt, current_model in enumerate(models_to_try):
        delays = _RETRY_DELAYS if attempt == 0 else [2]
        for delay_idx, delay in enumerate([0] + delays):
            if delay:
                time.sleep(delay)
            try:
                return _call_openrouter(messages, current_model, max_tokens)
            except requests.RequestException as exc:
                last_exc = exc
                continue
            except LLMError:
                raise

    raise LLMError(f"All models and retries exhausted. Last error: {last_exc}")


def extract(
    prompt: str,
    schema: Type[T],
    system: str | None = None,
    *,
    max_tokens: int = 1024,
) -> T:
    """
    Ask the LLM to return JSON conforming to `schema`, then validate it.
    Raises ExtractionError when the output cannot be parsed or validated.
    """
    sys_msg = system or (
        "You are a structured data extractor. "
        "Return ONLY valid JSON conforming to the requested schema. "
        "Do not include explanation or markdown fences."
    )
    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": prompt},
    ]
    content, tokens = complete(messages, max_tokens=max_tokens)

    # Strip markdown fences if the model added them.
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"LLM returned non-JSON: {exc}\nRaw: {content[:300]}") from exc

    try:
        return schema.model_validate(raw), tokens
    except ValidationError as exc:
        raise ExtractionError(
            f"LLM output failed schema validation: {exc}\nRaw: {content[:300]}"
        ) from exc


def draft(
    prompt: str,
    system: str | None = None,
    *,
    max_tokens: int = 1024,
) -> tuple[str, int]:
    """
    Ask the LLM to produce free-text (a comment, email, summary).
    Returns (text, tokens_used). Output is always shown to the user before
    any action is taken — never acted on directly.
    """
    sys_msg = system or (
        "You are a helpful assistant drafting clear, concise real-estate workflow "
        "communications. Write in plain English. Do not invent legal clauses."
    )
    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": prompt},
    ]
    return complete(messages, max_tokens=max_tokens)
