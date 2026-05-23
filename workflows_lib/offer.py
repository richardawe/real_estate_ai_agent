"""
Offer workflow step (buy path).

Drafts an offer letter using the LLM (never deciding the price — that's the
user's decision from the counter/intake data), attaches it as a HITL task,
and waits for /approve. On approval, generates a submission package comment.

The LLM is only used to format the letter from a template; the offer price,
contingencies, and completion date come from the issue front-matter, which
the user controls via /counter or the intake form.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.extractor import draft
from engine.state_machine import State, add_hitl, transition
from workflows_lib.issue_io import (
    get_field,
    parse_front_matter,
    render_front_matter,
    update_field,
)

_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts"


def _offer_price(fm: dict[str, Any]) -> int | None:
    tx = fm.get("current_transaction") or {}
    if isinstance(tx, dict):
        return tx.get("amount")
    return None


def draft_offer(
    issue_body: str,
    labels: list[str],
    *,
    property_details: dict[str, Any],
    buyer_name: str,
    rules: dict[str, Any] | None = None,
) -> tuple[str, list[str], str, int]:
    """
    Draft an offer letter for the selected property.

    Returns (new_body, new_labels, hitl_comment, tokens_used).
    The caller must post the hitl_comment and update the issue.
    The actual letter is subject to the user's /approve — not sent automatically.
    """
    fm, prose = parse_front_matter(issue_body)
    workflow_id = fm.get("workflow_id", "")
    requirements = fm.get("requirements", {})

    offer_price = _offer_price(fm) or requirements.get("budget_max")
    if not offer_price:
        raise ValueError("No offer price found in front-matter or requirements")

    if rules is None:
        import yaml
        rules_path = Path(__file__).parent.parent / "rules" / "buying_v1.yaml"
        with rules_path.open() as f:
            rules = yaml.safe_load(f)

    contingencies = rules.get("contingencies_required", ["inspection", "financing", "appraisal"])
    completion_date = requirements.get("move_in_by") or "TBD"
    property_address = property_details.get("address", "the selected property")

    template = (_PROMPTS_DIR / "offer_draft_v1.md").read_text()
    import json as _json
    prompt = template.format(
        property_json=_json.dumps(property_details),
        requirements_json=_json.dumps(requirements),
        offer_price=f"£{offer_price:,}",
        contingencies=", ".join(contingencies),
        completion_date=completion_date,
        buyer_name=buyer_name,
        workflow_id=workflow_id,
    )

    letter, tokens = draft(prompt)

    hitl_template = (_PROMPTS_DIR / "hitl" / "approve_offer.md").read_text()
    hitl_comment = hitl_template.format(
        property_address=property_address,
        offer_price=f"£{offer_price:,}",
        contingencies=", ".join(contingencies),
        completion_date=completion_date,
        offer_letter_text=letter,
    )

    # Record the draft in front-matter.
    fm["current_transaction"] = {
        "type": "offer",
        "amount": offer_price,
        "property_address": property_address,
        "draft_letter": letter,
    }
    new_body = render_front_matter(fm, prose)
    fm2, _ = parse_front_matter(new_body)
    new_body_with_tokens = update_field(
        new_body, "token_usage", (fm2.get("token_usage") or 0) + tokens
    )

    # Transition to offer_draft and add HITL label.
    new_labels = transition(labels, State.OFFER_DRAFT)
    new_labels = add_hitl(new_labels, "approve_offer")

    return new_body_with_tokens, new_labels, hitl_comment, tokens
