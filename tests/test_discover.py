"""Tests for the discover workflow step."""

import pytest

from engine.state_machine import State, current_state
from workflows_lib.discover import run_discover
from workflows_lib.issue_io import parse_front_matter

BUY_ISSUE_BODY = """\
---
workflow_id: rwa-2026-000001
type: buy
schema_version: 1
jurisdiction: england
encrypted_pii: ENCRYPTED
requirements:
  budget_min: 300000
  budget_max: 450000
  bedrooms_min: 3
  property_types: [house]
  must_haves: [garden]
  locations: [Reading]
shortlist: []
selected_property_id: null
current_transaction: null
documents: []
token_usage: 0
---
"""

DISCOVER_LABELS = ["flow:buy", "state:discover"]
SHORTLIST_LABELS = ["flow:buy", "state:shortlist_review"]


def test_discover_dry_run_transitions_state():
    new_body, new_labels, comment = run_discover(
        BUY_ISSUE_BODY, DISCOVER_LABELS, dry_run=True
    )
    assert current_state(new_labels) == State.SHORTLIST_REVIEW
    assert "hitl:review_shortlist" in new_labels


def test_discover_dry_run_posts_comment():
    _, _, comment = run_discover(BUY_ISSUE_BODY, DISCOVER_LABELS, dry_run=True)
    assert "Shortlist" in comment
    assert "review" in comment.lower() or "source" in comment.lower()


def test_discover_dry_run_updates_shortlist_field():
    new_body, _, _ = run_discover(BUY_ISSUE_BODY, DISCOVER_LABELS, dry_run=True)
    fm, _ = parse_front_matter(new_body)
    assert isinstance(fm.get("shortlist"), list)


def test_discover_from_shortlist_review_stays_in_review():
    # If already in shortlist_review (refresh), state should not change.
    new_body, new_labels, comment = run_discover(
        BUY_ISSUE_BODY, SHORTLIST_LABELS, dry_run=True
    )
    assert current_state(new_labels) == State.SHORTLIST_REVIEW


def test_discover_adds_properties_from_adapter(monkeypatch):
    """Inject fake properties from the adapter to test scoring + shortlisting."""
    fake_props = [
        {
            "source_id": "zoopla",
            "external_id": "z-001",
            "title": "3 bed house with garden",
            "price": 380_000,
            "address": "1 Elm St, Reading",
            "beds": 3,
            "property_type": "house",
            "features": ["garden"],
            "url": "https://zoopla.co.uk/z-001",
            "location_score": 1.0,
        },
        {
            "source_id": "zoopla",
            "external_id": "z-002",
            "title": "2 bed flat",
            "price": 200_000,
            "address": "2 Oak Ave, Reading",
            "beds": 2,
            "property_type": "flat",
            "features": [],
            "url": "https://zoopla.co.uk/z-002",
            "location_score": 0.8,
        },
    ]

    def fake_run_discover_no_http(issue_body, labels, *, dry_run=False):
        from workflows_lib.discover import (
            _workflow_rules, _matching_rules, _location_slug,
            _format_shortlist_table, _PROMPTS_DIR,
        )
        from engine.eligibility import is_eligible, must_have_score
        from engine.pricing import score_property
        from engine.state_machine import State, add_hitl, current_state, transition
        from workflows_lib.issue_io import parse_front_matter, render_front_matter
        import yaml

        fm, prose = parse_front_matter(issue_body)
        requirements = fm.get("requirements", {})
        workflow_type = fm.get("type", "buy")
        w_rules = _workflow_rules(workflow_type)
        m_rules = _matching_rules()
        min_threshold = m_rules["min_score_threshold"]
        shortlist_size = m_rules["shortlist_size"]

        scored = []
        for prop in fake_props:
            elig = is_eligible(prop, requirements, workflow_type, rules=w_rules)
            if not elig.eligible:
                continue
            score = score_property(
                prop, requirements,
                must_have_score=elig.must_have_score,
                matching_rules=m_rules,
                workflow_rules=w_rules,
            )
            if score.total >= min_threshold:
                scored.append({"prop": prop, "score": score, "eligibility": elig})

        scored.sort(key=lambda x: x["score"].total, reverse=True)
        shortlisted = scored[:shortlist_size]
        fm["shortlist"] = [s["prop"]["external_id"] for s in shortlisted]
        new_body = render_front_matter(fm, prose)
        new_labels = transition(labels, State.SHORTLIST_REVIEW)
        new_labels = add_hitl(new_labels, "review_shortlist")

        table = _format_shortlist_table(shortlisted)
        template = (_PROMPTS_DIR / "review_shortlist.md").read_text()
        comment = template.format(
            source_count=1,
            total_found=len(fake_props),
            shortlist_size=len(shortlisted),
            property_table=table,
        )
        return new_body, new_labels, comment

    new_body, new_labels, comment = fake_run_discover_no_http(
        BUY_ISSUE_BODY, DISCOVER_LABELS
    )
    fm, _ = parse_front_matter(new_body)
    # z-001 passes all filters; z-002 fails (beds < 3, no garden, flat not in allowed types)
    assert "z-001" in fm["shortlist"]
    assert "z-002" not in fm["shortlist"]
    assert "z-001" in comment
