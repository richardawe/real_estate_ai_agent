"""
Viewings scheduling step.

After the user likes properties from the shortlist, the agent:
1. Drafts viewing request emails for each liked property.
2. Posts a hitl:approve_viewing task with the suggested times.
3. On /approve, generates a submission package comment for the user to send.
4. On /approve (after viewings), transitions to offer_draft (buy) or application (rent).

The agent never sends emails directly — the user sends from their own account.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.state_machine import State, add_hitl, remove_hitl, transition
from workflows_lib.issue_io import get_field, parse_front_matter, render_front_matter, update_field

_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts"


def draft_viewing_requests(
    liked_properties: list[dict[str, Any]],
    buyer_name: str,
    availability_note: str = "",
) -> str:
    """
    Generate draft viewing request email text for each liked property.
    Returns a markdown string suitable for an issue comment.
    """
    if not liked_properties:
        return "_No liked properties to arrange viewings for._"

    sections = []
    for prop in liked_properties:
        address = prop.get("address", prop.get("external_id", "unknown"))
        sections.append(
            f"### {address}\n\n"
            f"**Draft email to send from your own account:**\n\n"
            f"> Subject: Viewing request — {address}\n>\n"
            f"> Dear Agent/Landlord,\n>\n"
            f"> I am interested in viewing the property at {address}. "
            f"Could you please arrange a viewing at your earliest convenience?\n>\n"
            + (f"> My availability: {availability_note}\n>\n" if availability_note else "")
            + f"> Kind regards,\n> {buyer_name}"
        )

    return "\n\n".join(sections)


def schedule_viewings(
    issue_body: str,
    labels: list[str],
    liked_properties: list[dict[str, Any]],
    buyer_name: str,
) -> tuple[str, list[str], str]:
    """
    Draft viewing requests and transition to state:viewings with a HITL task.

    Returns (new_body, new_labels, hitl_comment).
    """
    fm, prose = parse_front_matter(issue_body)
    user_notes = fm.get("user_notes", []) or []
    availability = user_notes[-1] if user_notes else ""

    drafts = draft_viewing_requests(liked_properties, buyer_name, availability)

    hitl_template = (_PROMPTS_DIR / "hitl" / "approve_viewing.md").read_text()
    prop_list = "\n".join(
        f"- {p.get('address', p.get('external_id', 'unknown'))}"
        for p in liked_properties
    )
    hitl_comment = hitl_template.format(
        property_list=prop_list,
        suggested_times="Based on your availability notes (add a `/note` with your free times).",
    ) + "\n\n---\n\n" + drafts

    new_labels = transition(labels, State.VIEWINGS)
    new_labels = add_hitl(new_labels, "approve_viewing")

    return issue_body, new_labels, hitl_comment
