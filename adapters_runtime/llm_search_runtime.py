"""
LLM-powered property discovery using Serper.dev + LLM extraction.

Uses Serper.dev (Google search API, free tier: 2,500 queries/month) to find
property listings, then feeds the returned snippets to the existing free
OpenRouter LLM for structured extraction in a single batch call.

Required env var: SERPER_API_KEY  (free at https://serper.dev)
Existing env var: OPENROUTER_API_KEY (unchanged)
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import requests
from pydantic import BaseModel

from engine.extractor import ExtractionError, extract

_SERPER_URL = "https://google.serper.dev/search"

_SITE_DOMAINS: dict[str, str] = {
    "rightmove": "rightmove.co.uk",
    "zoopla": "zoopla.co.uk",
    "spareroom": "spareroom.co.uk",
    "openrent": "openrent.co.uk",
    "craigslist": "craigslist.org",
}

_SNIPPET_CHARS = 300  # truncate each snippet to keep prompt tokens low


class _PropertyListing(BaseModel):
    address: str | None = None
    price: int | None = None
    rent_monthly: int | None = None
    beds: int | None = None
    property_type: str | None = None
    features: list[str] = []
    url: str = ""


class _PropertyListResult(BaseModel):
    properties: list[_PropertyListing] = []


def _serper_api_key() -> str:
    key = os.environ.get("SERPER_API_KEY", "")
    if not key:
        raise EnvironmentError("SERPER_API_KEY is not set")
    return key


def _build_query(
    source_id: str,
    workflow_type: str,
    requirements: dict[str, Any],
    location: str,
) -> str:
    site = _SITE_DOMAINS.get(source_id, source_id)
    parts = [f"site:{site}", location]

    beds_min = requirements.get("bedrooms_min")
    if beds_min:
        parts.append(f"{beds_min} bed")

    prop_types = requirements.get("property_types") or []
    if prop_types:
        parts.append(prop_types[0])

    if workflow_type == "buy":
        parts.append("for sale")
        b_max = requirements.get("budget_max")
        if b_max:
            parts.append(f"under £{b_max:,}")
    else:
        parts.append("to rent")
        r_max = requirements.get("rent_max")
        if r_max:
            parts.append(f"under £{r_max:,} pcm")

    return " ".join(parts)


def _search(query: str, max_results: int) -> list[dict[str, str]]:
    """Call Serper.dev Google Search API. Returns list of {title, url, body}."""
    resp = requests.post(
        _SERPER_URL,
        headers={
            "X-API-KEY": _serper_api_key(),
            "Content-Type": "application/json",
        },
        json={"q": query, "num": min(max_results, 20)},
        timeout=15,
    )
    resp.raise_for_status()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "body": r.get("snippet", ""),
        }
        for r in resp.json().get("organic", [])
    ]


def _url_id(source_id: str, url: str) -> str:
    return f"{source_id}-{hashlib.sha1(url.encode()).hexdigest()[:12]}"


def run_llm_search(
    source_id: str,
    workflow_type: str,
    requirements: dict[str, Any],
    location: str,
    *,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    Search for property listings via Serper.dev + LLM extraction.
    Returns property dicts compatible with the eligibility and scoring engine.
    Raises EnvironmentError if SERPER_API_KEY is missing.
    Returns an empty list on search or extraction failure.
    """
    query = _build_query(source_id, workflow_type, requirements, location)
    raw = _search(query, max_results)
    if not raw:
        return []

    snippets = "\n\n".join(
        f"[{i + 1}] Title: {r.get('title', '')}\n"
        f"    URL: {r.get('url', '')}\n"
        f"    Snippet: {r.get('body', '')[:_SNIPPET_CHARS]}"
        for i, r in enumerate(raw)
    )

    price_field = (
        "rent_monthly (integer, monthly rent in GBP)"
        if workflow_type == "rent"
        else "price (integer, sale price in GBP)"
    )

    prompt = (
        f"Extract individual property listings from these search results.\n\n"
        f"{snippets}\n\n"
        f'Return JSON: {{"properties": [...]}} where each item has:\n'
        f"- address (string or null)\n"
        f"- {price_field}\n"
        f"- beds (integer or null)\n"
        f"- property_type (e.g. flat, house, semi-detached, or null)\n"
        f'- features (list of strings, e.g. ["garden", "parking", "garage"])\n'
        f"- url (the result URL string)\n\n"
        f"Only include results that describe a single specific property listing. "
        f"Skip search pages, category pages, and non-property results."
    )

    try:
        result, _ = extract(prompt, _PropertyListResult, max_tokens=2048)
    except ExtractionError:
        return []

    props: list[dict[str, Any]] = []
    for p in result.properties:
        d = p.model_dump()
        d["source_id"] = source_id
        d["external_id"] = _url_id(source_id, d.get("url") or "")
        props.append(d)
    return props
