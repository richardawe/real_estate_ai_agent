"""
Tests for the buy and rent workflow step modules.
"""

import pytest
from unittest.mock import patch

from engine.state_machine import State, current_state, has_hitl
from workflows_lib.application import application_checklist_comment, check_fraud_signals
from workflows_lib.due_diligence import due_diligence_checklist_comment
from workflows_lib.issue_io import get_field, parse_front_matter
from workflows_lib.viewings import draft_viewing_requests, schedule_viewings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_VIEWINGS_BODY = """\
---
workflow_id: rwa-2026-000001
type: buy
schema_version: 1
jurisdiction: england
requirements:
  budget_max: 400000
  move_in_by: "2026-09-01"
shortlist: [z-001]
liked: [z-001]
user_notes: ["available weekday evenings"]
current_transaction: null
token_usage: 0
---
"""

SHORTLIST_LABELS = ["flow:buy", "state:shortlist_review", "hitl:review_shortlist"]
OFFER_SUBMITTED_LABELS = ["flow:buy", "state:offer_submitted"]
DUE_DILIGENCE_LABELS = ["flow:buy", "state:due_diligence"]


PROP = {
    "external_id": "z-001",
    "address": "42 Elm St, Reading",
    "price": 380_000,
    "beds": 3,
    "features": ["garden", "parking"],
    "url": "https://zoopla.co.uk/z-001",
}


# ---------------------------------------------------------------------------
# viewings.py
# ---------------------------------------------------------------------------


def test_draft_viewing_requests_includes_address():
    text = draft_viewing_requests([PROP], "Alice Smith", "weekday evenings")
    assert "42 Elm St" in text
    assert "Alice Smith" in text
    assert "weekday evenings" in text


def test_draft_viewing_requests_empty():
    text = draft_viewing_requests([], "Alice")
    assert "No liked properties" in text


def test_schedule_viewings_transitions_state():
    _, new_labels, comment = schedule_viewings(
        BASE_VIEWINGS_BODY, SHORTLIST_LABELS, [PROP], "Alice Smith"
    )
    assert current_state(new_labels) == State.VIEWINGS
    assert has_hitl(new_labels, "approve_viewing")


def test_schedule_viewings_comment_contains_address():
    _, _, comment = schedule_viewings(
        BASE_VIEWINGS_BODY, SHORTLIST_LABELS, [PROP], "Alice Smith"
    )
    assert "42 Elm St" in comment


# ---------------------------------------------------------------------------
# due_diligence.py
# ---------------------------------------------------------------------------


def test_due_diligence_checklist_buy():
    comment = due_diligence_checklist_comment(BASE_VIEWINGS_BODY, "buy")
    assert "Inspection Report" in comment or "inspection" in comment.lower()
    assert "/approve" in comment


def test_due_diligence_checklist_has_all_items():
    import yaml
    from pathlib import Path
    rules_path = Path(__file__).parent.parent / "rules" / "buying_v1.yaml"
    rules = yaml.safe_load(rules_path.read_text())
    checklist = rules.get("due_diligence_checklist", [])
    comment = due_diligence_checklist_comment(BASE_VIEWINGS_BODY, "buy")
    for item in checklist:
        assert item.replace("_", " ").lower() in comment.lower()


# ---------------------------------------------------------------------------
# application.py
# ---------------------------------------------------------------------------


def test_application_checklist_contains_docs():
    import yaml
    from pathlib import Path
    rules = yaml.safe_load((Path(__file__).parent.parent / "rules" / "renting_v1.yaml").read_text())
    docs = rules.get("required_application_docs", [])
    comment = application_checklist_comment(PROP)
    for doc in docs:
        assert doc.replace("_", " ").lower() in comment.lower()


def test_application_checklist_contains_property_address():
    comment = application_checklist_comment(PROP)
    assert "42 Elm St" in comment


def test_check_fraud_signals_below_market():
    listing = {"rent_monthly": 500}
    warnings = check_fraud_signals(listing, market_median_rent=1_500)
    assert len(warnings) >= 1
    assert "fraud" in warnings[0].lower() or "%" in warnings[0]


def test_check_fraud_signals_normal_rent():
    listing = {"rent_monthly": 1_400}
    warnings = check_fraud_signals(listing, market_median_rent=1_500)
    assert warnings == []


def test_check_fraud_signals_no_median():
    listing = {"rent_monthly": 500}
    # No median provided — cannot check price signal
    warnings = check_fraud_signals(listing, market_median_rent=None)
    assert not any("below" in w for w in warnings)


def test_check_fraud_upfront_payment():
    listing = {"rent_monthly": 1_400, "upfront_payment_required": True}
    warnings = check_fraud_signals(listing, market_median_rent=1_500)
    assert any("upfront" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# offer.py (LLM mocked)
# ---------------------------------------------------------------------------


def test_draft_offer_transitions_state():
    from workflows_lib.offer import draft_offer

    with patch("workflows_lib.offer.draft", return_value=("Dear vendor, we offer £380,000.", 30)):
        new_body, new_labels, comment, tokens = draft_offer(
            BASE_VIEWINGS_BODY,
            ["flow:buy", "state:viewings"],
            property_details=PROP,
            buyer_name="Alice Smith",
        )
    assert current_state(new_labels) == State.OFFER_DRAFT
    assert has_hitl(new_labels, "approve_offer")
    assert tokens == 30


def test_draft_offer_records_in_front_matter():
    from workflows_lib.offer import draft_offer

    with patch("workflows_lib.offer.draft", return_value=("letter text", 10)):
        new_body, _, _, _ = draft_offer(
            BASE_VIEWINGS_BODY,
            ["flow:buy", "state:viewings"],
            property_details=PROP,
            buyer_name="Alice Smith",
        )
    fm, _ = parse_front_matter(new_body)
    assert fm["current_transaction"]["amount"] == 400_000  # budget_max


def test_draft_offer_comment_contains_price():
    from workflows_lib.offer import draft_offer

    with patch("workflows_lib.offer.draft", return_value=("letter", 5)):
        _, _, comment, _ = draft_offer(
            BASE_VIEWINGS_BODY,
            ["flow:buy", "state:viewings"],
            property_details=PROP,
            buyer_name="Alice Smith",
        )
    assert "400,000" in comment or "400000" in comment


# ---------------------------------------------------------------------------
# lease.py (LLM mocked)
# ---------------------------------------------------------------------------


RENT_BODY = """\
---
workflow_id: rwr-2026-000002
type: rent
schema_version: 1
jurisdiction: england
requirements:
  rent_max: 1800
shortlist: []
token_usage: 0
---
"""

RENT_LABELS = ["flow:rent", "state:shortlist_review"]


def test_draft_lease_review_transitions_state():
    from workflows_lib.lease import draft_lease_review

    with patch("workflows_lib.lease.draft", return_value=("Summary: all clauses present.", 20)):
        new_body, new_labels, comment, tokens = draft_lease_review(
            RENT_BODY,
            RENT_LABELS,
            lease_text="This is a sample lease agreement.",
            property_details=PROP,
        )
    assert current_state(new_labels) == State.LEASE_REVIEW
    assert has_hitl(new_labels, "lease_review")


def test_draft_lease_review_comment_contains_summary():
    from workflows_lib.lease import draft_lease_review

    with patch("workflows_lib.lease.draft", return_value=("Summary: all clauses present.", 20)):
        _, _, comment, _ = draft_lease_review(
            RENT_BODY, RENT_LABELS,
            lease_text="lease text",
            property_details=PROP,
        )
    assert "Summary" in comment or "clauses" in comment.lower()
