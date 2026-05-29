"""
LLM-powered property discovery using SerpAPI + Serper.dev + LLM extraction.

Supports two Google search providers with automatic fallback:
  1. SerpAPI   (serpapi.com)   — set SERPAPI_API_KEY   (100 searches/month free)
  2. Serper.dev (serper.dev)   — set SERPER_API_KEY    (2,500 searches/month free)

Configure one or both. If both keys are present, SerpAPI is tried first; on
quota exhaustion or auth failure it falls back to Serper.dev automatically,
giving up to 2,600 free searches/month combined.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import requests
from pydantic import BaseModel

from engine.extractor import ExtractionError, extract

_SERPAPI_URL = "https://serpapi.com/search.json"
_SERPER_URL = "https://google.serper.dev/search"

_SITE_DOMAINS: dict[str, str] = {
    "rightmove": "rightmove.co.uk",
    "zoopla": "zoopla.co.uk",
    "spareroom": "spareroom.co.uk",
    "openrent": "openrent.co.uk",
    "onthemarket": "onthemarket.com",
    "gumtree_uk": "gumtree.com",
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


def _search_serpapi(query: str, max_results: int, key: str) -> list[dict[str, str]]:
    resp = requests.get(
        _SERPAPI_URL,
        params={"q": query, "num": min(max_results, 20), "api_key": key},
        timeout=15,
    )
    if resp.status_code in (401, 403, 429):
        raise RuntimeError(f"SerpAPI HTTP {resp.status_code}")
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("link", ""), "body": r.get("snippet", "")}
        for r in resp.json().get("organic_results", [])
    ]


def _search_serper(query: str, max_results: int, key: str) -> list[dict[str, str]]:
    resp = requests.post(
        _SERPER_URL,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        json={"q": query, "num": min(max_results, 20)},
        timeout=15,
    )
    if resp.status_code in (401, 403, 429):
        raise RuntimeError(f"Serper.dev HTTP {resp.status_code}")
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("link", ""), "body": r.get("snippet", "")}
        for r in resp.json().get("organic", [])
    ]


def _search(query: str, max_results: int) -> list[dict[str, str]]:
    """
    Try each configured search provider in order, falling back automatically.
    Raises EnvironmentError if no provider keys are configured.
    Raises RuntimeError if all configured providers fail.
    """
    providers = [
        ("SerpAPI",    "SERPAPI_API_KEY", _search_serpapi),
        ("Serper.dev", "SERPER_API_KEY",  _search_serper),
    ]

    configured = [(name, os.environ[env], fn) for name, env, fn in providers if os.environ.get(env)]

    if not configured:
        raise EnvironmentError(
            "No search provider configured. "
            "Set SERPAPI_API_KEY (serpapi.com) or SERPER_API_KEY (serper.dev) — or both."
        )

    last_error: Exception | None = None
    for name, key, fn in configured:
        try:
            return fn(query, max_results, key)
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"All search providers failed. Last error: {last_error}"
    )


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
    Search for property listings via Google (SerpAPI/Serper.dev) + LLM extraction.
    Returns property dicts compatible with the eligibility and scoring engine.
    Returns an empty list on extraction failure.
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
        # Skip listings the LLM could not extract a price for — they cannot
        # pass hard filters or be scored meaningfully.
        if p.price is None and p.rent_monthly is None:
            continue
        d = p.model_dump()
        d["source_id"] = source_id
        d["external_id"] = _url_id(source_id, d.get("url") or "")
        props.append(d)
    return props
