"""
Lease review workflow step (rent path).

Loads the appropriate offer-form adapter for the jurisdiction, generates
a lease diff/summary using the LLM (summary only — the LLM may not add
or alter legal clauses), and posts a hitl:lease_review task.

The agent never signs or e-signs without explicit /approve.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from engine.extractor import draft
from engine.state_machine import State, add_hitl, transition
from workflows_lib.issue_io import parse_front_matter, render_front_matter, update_field

_ADAPTERS_DIR = Path(__file__).parent.parent / "adapters" / "offer_forms"
_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts"


def _load_form_adapter(jurisdiction: str) -> dict[str, Any] | None:
    for path in _ADAPTERS_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(path.read_text())
        if cfg.get("jurisdiction") == jurisdiction:
            return cfg
    return None


def draft_lease_review(
    issue_body: str,
    labels: list[str],
    *,
    lease_text: str,
    property_details: dict[str, Any],
) -> tuple[str, list[str], str, int]:
    """
    Summarise a lease for user review.

    Returns (new_body, new_labels, hitl_comment, tokens_used).
    The LLM summarises must-haves and flags missing clauses; it does not
    rewrite or add legal text.
    """
    fm, prose = parse_front_matter(issue_body)
    jurisdiction = fm.get("jurisdiction", "england")

    adapter = _load_form_adapter(jurisdiction)
    must_haves = []
    if adapter:
        must_haves = []
        import yaml as _yaml
        rules_path = Path(__file__).parent.parent / "rules" / "renting_v1.yaml"
        with rules_path.open() as f:
            rent_rules = _yaml.safe_load(f)
        must_haves = rent_rules.get("lease_must_haves", [])

    prompt = (
        f"Summarise the following lease for a layperson tenant. "
        f"Flag any of these required clauses that are missing or unclear: "
        f"{', '.join(must_haves)}. "
        f"Do not add legal clauses. Do not give legal advice. "
        f"Output plain English bullet points.\n\nLease text:\n{lease_text[:4000]}"
    )

    summary, tokens = draft(prompt)

    hitl_comment = (
        "## Lease ready for review\n\n"
        f"**Property:** {property_details.get('address', 'the selected property')}\n\n"
        "I've summarised the key points below. Have your solicitor review the full "
        "document before approving.\n\n"
        + summary
        + "\n\n"
        "Reply `/approve` to proceed to e-sign, or `/reject` to renegotiate."
    )

    new_body = update_field(
        issue_body, "token_usage", (fm.get("token_usage") or 0) + tokens
    )
    new_labels = transition(labels, State.LEASE_REVIEW)
    new_labels = add_hitl(new_labels, "lease_review")

    return new_body, new_labels, hitl_comment, tokens
