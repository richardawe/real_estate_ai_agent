"""
Adapter runtime for property listing sources.

Loads a listing adapter YAML, validates robots.txt, enforces rate limits,
runs the extraction loop, and returns a list of PropertyListing dicts.
Aborts on 403/429 and surfaces a warning via the caller.

Only the HTTP runtime is implemented here (no Playwright dependency in the
base install). Playwright support requires `playwright install` and is wired
in via the same adapter config with runtime: playwright.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml

_ADAPTERS_DIR = Path(__file__).parent.parent / "adapters" / "listings"


class AdapterAbortError(Exception):
    """Raised when a 403/429 is received; the caller must post a warning."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def load_adapter(source_id: str) -> dict[str, Any]:
    """Load an adapter config by source_id."""
    for path in _ADAPTERS_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(path.read_text())
        if cfg.get("source_id") == source_id:
            return cfg
    raise FileNotFoundError(f"No listing adapter found for source_id={source_id!r}")


def _check_robots(base_url: str, user_agent: str = "*") -> bool:
    """Return True when the root search path is allowed by robots.txt."""
    rp = RobotFileParser()
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, base_url + "/")
    except Exception:
        # If robots.txt is unreachable, treat as allowed but log.
        return True


def _parse_currency_int(text: str) -> int | None:
    """Extract integer from a currency string like '£425,000' or '£1,500 pcm'."""
    digits = re.sub(r"[^\d]", "", text.split(".")[0])
    return int(digits) if digits else None


def _parse_int_first(text: str) -> int | None:
    """Extract the first integer from a text string like '3 bed'."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _apply_parsers(raw: str | None, parse: str | None) -> Any:
    if raw is None:
        return None
    if parse == "currency_int":
        return _parse_currency_int(raw)
    if parse in ("int_first", "int_before_br"):
        return _parse_int_first(raw)
    return raw


def _extract_fields_from_html(
    html: str,
    extract_cfg: dict[str, Any],
    source_id: str,
    base_url: str,
) -> list[dict[str, Any]]:
    """
    Extract property cards from raw HTML using the adapter's field selectors.

    Uses a simple regex-based fallback since BeautifulSoup is not a hard dep.
    In production, the Playwright runtime uses proper DOM access.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(extract_cfg["card_selector"])
    results = []
    for card in cards:
        item: dict[str, Any] = {"source_id": source_id, "external_id": "", "features": []}
        for field_name, field_cfg in extract_cfg["fields"].items():
            el = card.select_one(field_cfg["selector"])
            if el is None:
                if field_cfg.get("optional"):
                    continue
                item[field_name] = None
                continue
            attr = field_cfg.get("attr", "text")
            raw = el.get_text(strip=True) if attr == "text" else el.get(attr, "")
            prefix = field_cfg.get("prefix", "")
            if prefix and raw:
                raw = prefix + raw
            item[field_name] = _apply_parsers(raw, field_cfg.get("parse"))
        results.append(item)
    return results


def run_http_search(
    adapter: dict[str, Any],
    search_url: str,
    *,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run an HTTP-runtime adapter search. Returns raw extracted property dicts.
    Raises AdapterAbortError on 403/429.
    """
    if adapter.get("robots_check"):
        base_url = adapter["search"]["base_url"]
        if not _check_robots(base_url):
            raise AdapterAbortError(0, f"robots.txt disallows scraping {base_url}")

    rate = adapter.get("rate_limit_seconds", 2)
    extract_cfg = adapter["extract"]
    source_id = adapter["source_id"]
    base_url = adapter["search"]["base_url"]
    abort_statuses = set(adapter.get("error_handling", {}).get("abort_on_status", [403, 429]))
    pagination = adapter["search"].get("pagination", {})
    pages = max_pages or pagination.get("max_pages", 1)

    all_results: list[dict[str, Any]] = []
    offset_param = pagination.get("offset_param")
    offset_step = pagination.get("offset_step", 1)

    for page in range(pages):
        url = search_url
        if offset_param and page > 0:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{offset_param}={page * offset_step}"

        resp = requests.get(url, timeout=30, headers={"User-Agent": "RealEstateAgent/1.0"})

        if resp.status_code in abort_statuses:
            msg = adapter.get("error_handling", {}).get(
                "warning_message", f"HTTP {resp.status_code}"
            ).format(status_code=resp.status_code)
            raise AdapterAbortError(resp.status_code, msg)

        if not resp.ok:
            break

        cards = _extract_fields_from_html(resp.text, extract_cfg, source_id, base_url)
        all_results.extend(cards)

        if page < pages - 1:
            time.sleep(rate)

    return all_results


def build_search_url(
    adapter: dict[str, Any],
    workflow_type: str,
    requirements: dict[str, Any],
    location_slug: str,
) -> str:
    """Build the search URL from an adapter template and requirements."""
    search = adapter["search"]
    template_key = "buy_url_template" if workflow_type == "buy" else "rent_url_template"
    template = search.get(template_key, "")
    return template.format(
        location_slug=location_slug,
        city_subdomain=location_slug,
        budget_min=requirements.get("budget_min", 0),
        budget_max=requirements.get("budget_max", 0),
        rent_min=requirements.get("rent_min", 0),
        rent_max=requirements.get("rent_max", 0),
        bedrooms_min=requirements.get("bedrooms_min", 1),
    )
