"""
Discover workflow step: scrape listing sources, score, and post a shortlist.

Called by the discover GitHub Actions workflow for issues in state:discover
or state:shortlist_review (refresh). Reads requirements from issue front-matter,
runs adapters, filters + ranks via the deterministic engine, posts the top N
as a HITL comment, and transitions the issue to state:shortlist_review.

Token usage is accumulated in the front-matter's token_usage field.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from adapters_runtime.listings_runtime import (
    AdapterAbortError,
    build_search_url,
    load_adapter,
    run_http_search,
)
from engine.eligibility import is_eligible, must_have_score
from engine.pricing import score_property
from engine.state_machine import State, add_hitl, current_state, transition
from workflows_lib.issue_io import (
    get_field,
    parse_front_matter,
    render_front_matter,
    update_field,
)

_RULES_DIR = Path(__file__).parent.parent / "rules"
_ADAPTERS_DIR = Path(__file__).parent.parent / "adapters" / "listings"
_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts" / "hitl"


def _load_rules(filename: str) -> dict[str, Any]:
    with (_RULES_DIR / filename).open() as f:
        return yaml.safe_load(f)


def _matching_rules() -> dict[str, Any]:
    return _load_rules("matching_v1.yaml")


def _workflow_rules(workflow_type: str) -> dict[str, Any]:
    name = "buying_v1.yaml" if workflow_type == "buy" else "renting_v1.yaml"
    return _load_rules(name)


def _source_ids_for_jurisdiction(jurisdiction: str, workflow_type: str = "buy") -> list[str]:
    """Return adapter source_ids appropriate for a jurisdiction and workflow type."""
    mapping: dict[str, dict[str, list[str]]] = {
        "england": {
            "buy": ["rightmove"],
            "rent": ["spareroom", "openrent"],
        },
        "us_ca": {
            "buy": ["craigslist"],
            "rent": ["craigslist"],
        },
    }
    return mapping.get(jurisdiction, {}).get(workflow_type, [])


def _location_slug(location: str) -> str:
    """Convert a human location name to a URL slug (basic normalisation)."""
    return location.lower().replace(" ", "-").replace(",", "")


def _format_shortlist_table(shortlisted: list[dict[str, Any]]) -> str:
    """Render a markdown table of shortlisted properties."""
    header = "| # | Address | Price | Beds | Score | Link | ID |\n"
    sep = "|---|---------|-------|------|-------|------|----||\n"
    rows = ""
    for i, item in enumerate(shortlisted, 1):
        prop = item["prop"]
        score = item["score"]
        price = prop.get("price") or prop.get("rent_monthly") or "N/A"
        price_str = f"£{price:,}" if isinstance(price, int) else str(price)
        url = prop.get("url", "")
        rows += (
            f"| {i} | {prop.get('address', 'N/A')} | {price_str} "
            f"| {prop.get('beds', '?')} | {score.total:.2f} "
            f"| [View]({url}) | `{prop.get('external_id', '')}` |\n"
        )
    return header + sep + rows


def run_discover(
    issue_body: str,
    labels: list[str],
    *,
    dry_run: bool = False,
) -> tuple[str, list[str], str]:
    """
    Main entry point for the discover step.

    Returns (new_issue_body, new_labels, hitl_comment_text).
    When dry_run=True, no external HTTP calls are made (adapters are skipped).
    """
    fm, prose = parse_front_matter(issue_body)
    requirements: dict[str, Any] = fm.get("requirements", {})
    workflow_type: str = fm.get("type", "buy")
    jurisdiction: str = fm.get("jurisdiction", "unknown")
    workflow_id: str = fm.get("workflow_id", "")

    w_rules = _workflow_rules(workflow_type)
    m_rules = _matching_rules()
    min_threshold: float = m_rules["min_score_threshold"]
    shortlist_size: int = m_rules["shortlist_size"]

    source_ids = _source_ids_for_jurisdiction(jurisdiction, workflow_type)
    all_props: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not dry_run:
        for source_id in source_ids:
            try:
                adapter = load_adapter(source_id)
            except FileNotFoundError:
                continue

            for location in requirements.get("locations", []):
                slug = _location_slug(location)
                url = build_search_url(adapter, workflow_type, requirements, slug)
                try:
                    props = run_http_search(adapter, url)
                    for p in props:
                        p.setdefault("external_id", f"{source_id}-{hash(p.get('url', ''))}")
                    all_props.extend(props)
                except AdapterAbortError as e:
                    warnings.append(e.message)

    # Score and filter.
    scored: list[dict[str, Any]] = []
    for prop in all_props:
        elig = is_eligible(prop, requirements, workflow_type, rules=w_rules)
        if not elig.eligible:
            continue
        score = score_property(
            prop,
            requirements,
            must_have_score=elig.must_have_score,
            matching_rules=m_rules,
            workflow_rules=w_rules,
        )
        if score.total >= min_threshold:
            scored.append({"prop": prop, "score": score, "eligibility": elig})

    scored.sort(key=lambda x: x["score"].total, reverse=True)
    shortlisted = scored[:shortlist_size]

    # Update front-matter shortlist.
    shortlist_ids = [s["prop"].get("external_id", "") for s in shortlisted]
    fm["shortlist"] = shortlist_ids
    new_body = render_front_matter(fm, prose)

    # Transition state.
    state = current_state(labels)
    if state == State.DISCOVER:
        new_labels = transition(labels, State.SHORTLIST_REVIEW)
    else:
        new_labels = list(labels)
    new_labels = add_hitl(new_labels, "review_shortlist")

    # Build HITL comment from template.
    template = (_PROMPTS_DIR / "review_shortlist.md").read_text()
    table = _format_shortlist_table(shortlisted) if shortlisted else "_No matching properties found._"
    comment = template.format(
        source_count=len(source_ids),
        total_found=len(all_props),
        shortlist_size=len(shortlisted),
        property_table=table,
    )
    if warnings:
        comment += "\n\n**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings)

    return new_body, new_labels, comment
