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


def handle_approve(
    body: str, labels: list[str], _arg: Optional[str]
) -> CommandResult:
    """
    /approve — approves the most recent pending HITL task.

    Finds the first hitl:<kind> label and removes it. If the current state
    has a natural next step, transitions there. Otherwise stays put.
    """
    hitl_labels = [l for l in labels if l.startswith("hitl:")]
    if not hitl_labels:
        return CommandResult(body, labels, "No pending task to approve.")

    kind = hitl_labels[0][len("hitl:"):]
    new_labels = remove_hitl(labels, kind)

    # Approving the shortlist review → schedule viewings for liked properties.
    if kind == "review_shortlist":
        from workflows_lib.viewings import schedule_viewings
        fm, _ = parse_front_matter(body)
        liked_ids: list[str] = fm.get("liked", []) or []
        all_props: list[dict] = fm.get("shortlist_properties", []) or []
        liked_props = [p for p in all_props if p.get("external_id") in liked_ids]
        if not liked_props:
            return CommandResult(
                body, new_labels,
                "No liked properties found. Use `/like <property_id>` on at least one property first."
            )
        buyer_name: str = fm.get("requirements", {}).get("applicant_name", "Applicant")
        new_body, new_labels, hitl_comment = schedule_viewings(body, new_labels, liked_props, buyer_name)
        return CommandResult(new_body, new_labels, hitl_comment)

    # State advances triggered by /approve for other HITL tasks.
    state = current_state(new_labels)
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
