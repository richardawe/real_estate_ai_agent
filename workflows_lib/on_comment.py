"""
Slash-command parser and router for issue comments.

Called by the on_comment GitHub Actions workflow whenever a comment is created
on a workflow issue. Parses the comment body for a slash-command, validates it,
and dispatches to the appropriate handler.

Handlers must never take an external action without an explicit /approve.
All state writes go through state_machine.transition() and issue_io.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from engine.state_machine import (
    State,
    add_hitl,
    current_state,
    has_hitl,
    remove_hitl,
    transition,
)
from workflows_lib.issue_io import (
    append_to_list,
    get_field,
    parse_front_matter,
    remove_from_list,
    render_front_matter,
    update_field,
)

_COMMAND_RE = re.compile(r"^/(\w+)(?:\s+(.+))?$", re.MULTILINE)


@dataclass
class ParsedCommand:
    name: str
    arg: Optional[str]


@dataclass
class CommandResult:
    new_body: str
    new_labels: list[str]
    reply: str              # Comment text to post back


class UnknownCommandError(Exception):
    pass


class CommandNotAllowedError(Exception):
    """Raised when the command is not valid in the current workflow state."""
    pass


def parse_command(comment_body: str) -> Optional[ParsedCommand]:
    """Extract the first slash-command from a comment body."""
    m = _COMMAND_RE.search(comment_body.strip())
    if not m:
        return None
    return ParsedCommand(name=m.group(1).lower(), arg=(m.group(2) or "").strip() or None)


def _build_contact_reply(fm: dict, workflow_type: str) -> str:
    liked = fm.get("liked") or []
    requirements = fm.get("requirements") or {}
    name = requirements.get("full_name") or "I"
    beds = requirements.get("bedrooms_min", "")
    beds_str = f"{beds}-bedroom " if beds else ""

    if not liked:
        if workflow_type == "rent":
            return (
                "Shortlist approved — moving to the next step.\n\n"
                "_Tip: use `/like <id>` on properties you want to pursue "
                "and I'll generate ready-to-send viewing request templates._"
            )
        return (
            "Shortlist approved — viewing stage started.\n\n"
            "_Tip: use `/like <id>` on properties you want to view "
            "and I'll generate contact templates for the agents._"
        )

    header = (
        "## Viewing request templates\n\n"
        "Here are ready-to-send messages for each property you liked. "
        "Visit each listing link and send this to the agent or landlord:\n\n"
    )
    blocks = []
    for pid in liked:
        if workflow_type == "rent":
            msg = (
                "Subject: Viewing enquiry\n\n"
                "Hello,\n\n"
                f"I came across this property listing and I'm very interested in arranging a viewing.\n\n"
                f"I'm looking for a {beds_str}property to rent and yours matches my requirements well. "
                "I'd love to visit at your earliest convenience — please let me know available times.\n\n"
                f"Kind regards,\n{name}"
            )
        else:
            budget_max = requirements.get("budget_max")
            budget_str = f"£{budget_max:,}" if isinstance(budget_max, int) else "within my budget"
            ftb = " (first-time buyer)" if requirements.get("first_time_buyer") else ""
            msg = (
                "Subject: Viewing request\n\n"
                "Hello,\n\n"
                "I'm interested in viewing this property and would like to arrange an appointment "
                "at your earliest convenience.\n\n"
                f"I'm a{ftb} buyer looking for a {beds_str}property with a budget of {budget_str}.\n\n"
                f"Kind regards,\n{name}"
            )
        blocks.append(f"### Property `{pid}`\n\n```\n{msg}\n```")
    return header + "\n\n---\n\n".join(blocks)


def _build_offer_submission_reply(fm: dict) -> str:
    tx = fm.get("current_transaction") or {}
    if not isinstance(tx, dict) or not tx:
        return "Offer approved. Send the draft letter from the previous comment to the estate agent."
    letter = tx.get("draft_letter", "")
    address = tx.get("property_address", "the selected property")
    amount = tx.get("amount")
    amount_str = f"£{amount:,}" if isinstance(amount, int) else "as discussed"
    return (
        f"## Offer submission package\n\n"
        f"Your offer of **{amount_str}** for **{address}** has been approved.\n\n"
        f"### Send this to the estate agent\n\n"
        f"Find the agent's contact details on the listing page and email them this letter:\n\n"
        f"```\n{letter}\n```\n\n"
        "Once you receive a response, reply here and I'll help with the next steps."
    )


def handle_approve(
    body: str, labels: list[str], _arg: Optional[str]
) -> CommandResult:
    """
    /approve — approves the most recent pending HITL task.

    Finds the first hitl:<kind> label and removes it. Routes to specialised
    handlers for review_shortlist (generates contact templates + advances state)
    and approve_offer (generates submission package + advances state).
    """
    hitl_labels = [l for l in labels if l.startswith("hitl:")]
    if not hitl_labels:
        return CommandResult(body, labels, "No pending task to approve.")

    kind = hitl_labels[0][len("hitl:"):]
    new_labels = remove_hitl(labels, kind)

    fm, _ = parse_front_matter(body)
    workflow_type = fm.get("type", "buy")
    state = current_state(new_labels)

    # Shortlist approval: advance state and generate viewing contact templates.
    if kind == "review_shortlist" and state == State.SHORTLIST_REVIEW:
        next_state = State.LEASE_REVIEW if workflow_type == "rent" else State.VIEWINGS
        new_labels = transition(new_labels, next_state)
        return CommandResult(body, new_labels, _build_contact_reply(fm, workflow_type))

    # Offer approval: advance state and generate submission package.
    if kind == "approve_offer" and state == State.OFFER_DRAFT:
        new_labels = transition(new_labels, State.OFFER_SUBMITTED)
        return CommandResult(body, new_labels, _build_offer_submission_reply(fm))

    # Generic advances for remaining HITL kinds.
    advance_map = {
        State.OFFER_DRAFT: State.OFFER_SUBMITTED,
        State.LEASE_REVIEW: State.CLOSING,
    }
    if state in advance_map:
        new_labels = transition(new_labels, advance_map[state])

    reply = f"Approved `hitl:{kind}`. Moving to the next step."
    return CommandResult(body, new_labels, reply)


def handle_reject(
    body: str, labels: list[str], _arg: Optional[str]
) -> CommandResult:
    """
    /reject — rejects the most recent pending HITL task.

    Removes the hitl label. For offer drafts, returns to shortlist_review.
    """
    hitl_labels = [l for l in labels if l.startswith("hitl:")]
    if not hitl_labels:
        return CommandResult(body, labels, "No pending task to reject.")

    kind = hitl_labels[0][len("hitl:"):]
    new_labels = remove_hitl(labels, kind)

    state = current_state(new_labels)
    if state == State.OFFER_DRAFT:
        new_labels = transition(new_labels, State.SHORTLIST_REVIEW)

    reply = f"Rejected `hitl:{kind}`. Returning to the previous step."
    return CommandResult(body, new_labels, reply)


def handle_counter(
    body: str, labels: list[str], arg: Optional[str]
) -> CommandResult:
    """
    /counter <amount> — records a counter-offer amount for the agent to use.

    The agent will draft a new offer at this amount awaiting another /approve.
    """
    if not arg:
        return CommandResult(body, labels, "Usage: `/counter <amount>` (e.g. `/counter 395000`)")

    cleaned = re.sub(r"[£$,\s]", "", arg)
    try:
        amount = int(cleaned)
    except ValueError:
        return CommandResult(body, labels, f"Could not parse amount from: {arg!r}")

    new_body = update_field(body, "current_transaction", {"type": "counter", "amount": amount})
    new_labels = remove_hitl(labels, "counter_decision")
    new_labels = add_hitl(new_labels, "approve_offer")

    reply = f"Counter-offer of {amount:,} recorded. I'll draft an updated offer for your review."
    return CommandResult(new_body, new_labels, reply)


def handle_like(
    body: str, labels: list[str], arg: Optional[str]
) -> CommandResult:
    """
    /like <property_id> — adds a property to the user's liked shortlist.
    """
    if not arg:
        return CommandResult(body, labels, "Usage: `/like <property_id>`")
    new_body = append_to_list(body, "liked", arg)
    reply = f"Added `{arg}` to your liked properties."
    return CommandResult(new_body, labels, reply)


def handle_skip(
    body: str, labels: list[str], arg: Optional[str]
) -> CommandResult:
    """
    /skip <property_id> — removes a property from the shortlist.
    """
    if not arg:
        return CommandResult(body, labels, "Usage: `/skip <property_id>`")
    new_body = remove_from_list(body, "shortlist", arg)
    reply = f"Removed `{arg}` from your shortlist."
    return CommandResult(new_body, labels, reply)


def handle_note(
    body: str, labels: list[str], arg: Optional[str]
) -> CommandResult:
    """
    /note <text> — appends context for the agent's next pass.
    """
    if not arg:
        return CommandResult(body, labels, "Usage: `/note <your context>`")
    fm, rest = parse_front_matter(body)
    notes: list[str] = fm.get("user_notes", []) or []
    notes.append(arg)
    fm["user_notes"] = notes
    new_body = render_front_matter(fm, rest)
    reply = "Note recorded. I'll take it into account on the next pass."
    return CommandResult(new_body, labels, reply)


def handle_abort(
    body: str, labels: list[str], _arg: Optional[str]
) -> CommandResult:
    """
    /abort — purges PII and closes the workflow.

    The encrypted_pii field is zeroed; the issue will be closed by the
    caller after this returns.
    """
    from engine.crypto import purge_encrypted_block
    from workflows_lib.issue_io import get_field

    encrypted = get_field(body, "encrypted_pii", "")
    if encrypted:
        zeroed = purge_encrypted_block(encrypted)
        new_body = update_field(body, "encrypted_pii", zeroed)
    else:
        new_body = body

    new_labels = [l for l in labels if not l.startswith("hitl:") and not l.startswith("state:")]
    new_labels.append(State.COMPLETED.value)

    reply = (
        "Workflow aborted. All encrypted PII has been purged. "
        "This issue will be closed."
    )
    return CommandResult(new_body, new_labels, reply)


_HANDLERS: dict[str, Callable[[str, list[str], Optional[str]], CommandResult]] = {
    "approve": handle_approve,
    "reject": handle_reject,
    "counter": handle_counter,
    "like": handle_like,
    "skip": handle_skip,
    "note": handle_note,
    "abort": handle_abort,
}


def dispatch(
    comment_body: str,
    issue_body: str,
    labels: list[str],
) -> Optional[CommandResult]:
    """
    Parse and dispatch a slash-command from a comment.
    Returns None when the comment contains no slash-command.
    Raises UnknownCommandError for unrecognised commands.
    """
    cmd = parse_command(comment_body)
    if cmd is None:
        return None
    handler = _HANDLERS.get(cmd.name)
    if handler is None:
        raise UnknownCommandError(
            f"Unknown command: `/{cmd.name}`. "
            f"Valid commands: {', '.join('/' + k for k in _HANDLERS)}"
        )
    return handler(issue_body, labels, cmd.arg)
