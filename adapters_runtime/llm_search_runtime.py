"""
LLM-powered property discovery using DuckDuckGo + LLM extraction.

Replaces the HTTP scraper runtime. Uses DuckDuckGo to find property listings
via text search, then feeds the returned snippets to the LLM for structured
extraction in a single call. No extra API keys required — uses the existing
OPENROUTER_API_KEY and DuckDuckGo's public search interface.
"""

from __future__ import annotations

import hashlib
from typing import Any

from duckduckgo_search import DDGS
from pydantic import BaseModel

from engine.extractor import ExtractionError, extract

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
    try:
        return list(DDGS().text(query, max_results=max_results))
    except Exception:
        return []


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
    Search for property listings via DuckDuckGo + LLM extraction.
    Returns property dicts compatible with the eligibility and scoring engine.
    Raises no exceptions — returns an empty list on any failure.
    """
    query = _build_query(source_id, workflow_type, requirements, location)
    raw = _search(query, max_results)
    if not raw:
        return []

    snippets = "\n\n".join(
        f"[{i + 1}] Title: {r.get('title', '')}\n"
        f"    URL: {r.get('href', '')}\n"
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
        f"- features (list of strings, e.g. [\"garden\", \"parking\", \"garage\"])\n"
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
