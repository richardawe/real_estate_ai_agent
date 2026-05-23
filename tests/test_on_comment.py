"""Tests for the slash-command parser and dispatcher."""

import pytest

from engine.state_machine import State, current_state, has_hitl
from workflows_lib.issue_io import get_field, parse_front_matter
from workflows_lib.on_comment import (
    CommandResult,
    UnknownCommandError,
    dispatch,
    handle_abort,
    handle_approve,
    handle_counter,
    handle_like,
    handle_note,
    handle_reject,
    handle_skip,
    parse_command,
)

BASE_BODY = """\
---
workflow_id: rwa-2026-000001
type: buy
schema_version: 1
shortlist: [prop-001, prop-002]
liked: []
encrypted_pii: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==
current_transaction: null
---
"""

OFFER_DRAFT_LABELS = ["flow:buy", "state:offer_draft", "hitl:approve_offer"]
DISCOVER_LABELS = ["flow:buy", "state:discover"]
SHORTLIST_LABELS = ["flow:buy", "state:shortlist_review", "hitl:review_shortlist"]


# ---------------------------------------------------------------------------
# parse_command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,name,arg", [
    ("/approve", "approve", None),
    ("/reject", "reject", None),
    ("/counter 395000", "counter", "395000"),
    ("/like prop-001", "like", "prop-001"),
    ("/skip prop-002", "skip", "prop-002"),
    ("/note please find more options", "note", "please find more options"),
    ("/abort", "abort", None),
])
def test_parse_command_valid(text, name, arg):
    cmd = parse_command(text)
    assert cmd is not None
    assert cmd.name == name
    assert cmd.arg == arg


def test_parse_command_none_for_plain_comment():
    assert parse_command("this is just a comment") is None


def test_parse_command_in_multiline_comment():
    comment = "I've reviewed the shortlist.\n\n/like prop-001\n"
    cmd = parse_command(comment)
    assert cmd is not None
    assert cmd.name == "like"


# ---------------------------------------------------------------------------
# handle_approve
# ---------------------------------------------------------------------------


def test_approve_removes_hitl_label():
    result = handle_approve(BASE_BODY, OFFER_DRAFT_LABELS, None)
    assert not has_hitl(result.new_labels, "approve_offer")


def test_approve_offer_draft_transitions_to_submitted():
    result = handle_approve(BASE_BODY, OFFER_DRAFT_LABELS, None)
    assert current_state(result.new_labels) == State.OFFER_SUBMITTED


def test_approve_with_no_hitl_returns_message():
    result = handle_approve(BASE_BODY, DISCOVER_LABELS, None)
    assert "No pending task" in result.reply


# ---------------------------------------------------------------------------
# handle_reject
# ---------------------------------------------------------------------------


def test_reject_removes_hitl_label():
    result = handle_reject(BASE_BODY, OFFER_DRAFT_LABELS, None)
    assert not has_hitl(result.new_labels, "approve_offer")


def test_reject_offer_draft_returns_to_shortlist():
    result = handle_reject(BASE_BODY, OFFER_DRAFT_LABELS, None)
    assert current_state(result.new_labels) == State.SHORTLIST_REVIEW


def test_reject_no_hitl_returns_message():
    result = handle_reject(BASE_BODY, DISCOVER_LABELS, None)
    assert "No pending task" in result.reply


# ---------------------------------------------------------------------------
# handle_counter
# ---------------------------------------------------------------------------


def test_counter_records_amount():
    labels = ["flow:buy", "state:offer_draft", "hitl:counter_decision"]
    result = handle_counter(BASE_BODY, labels, "£395,000")
    fm, _ = parse_front_matter(result.new_body)
    assert fm["current_transaction"]["amount"] == 395_000


def test_counter_adds_approve_offer_hitl():
    labels = ["flow:buy", "state:offer_draft", "hitl:counter_decision"]
    result = handle_counter(BASE_BODY, labels, "395000")
    assert has_hitl(result.new_labels, "approve_offer")


def test_counter_invalid_amount():
    result = handle_counter(BASE_BODY, DISCOVER_LABELS, "not a number")
    assert "Could not parse" in result.reply


def test_counter_no_arg():
    result = handle_counter(BASE_BODY, DISCOVER_LABELS, None)
    assert "Usage" in result.reply


# ---------------------------------------------------------------------------
# handle_like / handle_skip
# ---------------------------------------------------------------------------


def test_like_adds_to_liked():
    result = handle_like(BASE_BODY, SHORTLIST_LABELS, "prop-003")
    assert get_field(result.new_body, "liked") == ["prop-003"]


def test_like_idempotent():
    body = BASE_BODY
    result1 = handle_like(body, SHORTLIST_LABELS, "prop-001")
    result2 = handle_like(result1.new_body, SHORTLIST_LABELS, "prop-001")
    assert get_field(result2.new_body, "liked").count("prop-001") == 1


def test_skip_removes_from_shortlist():
    result = handle_skip(BASE_BODY, SHORTLIST_LABELS, "prop-001")
    shortlist = get_field(result.new_body, "shortlist")
    assert "prop-001" not in shortlist
    assert "prop-002" in shortlist


# ---------------------------------------------------------------------------
# handle_note
# ---------------------------------------------------------------------------


def test_note_appended():
    result = handle_note(BASE_BODY, DISCOVER_LABELS, "please find properties near train station")
    notes = get_field(result.new_body, "user_notes")
    assert "train station" in notes[0]


def test_multiple_notes_accumulated():
    r1 = handle_note(BASE_BODY, DISCOVER_LABELS, "first note")
    r2 = handle_note(r1.new_body, DISCOVER_LABELS, "second note")
    notes = get_field(r2.new_body, "user_notes")
    assert len(notes) == 2


# ---------------------------------------------------------------------------
# handle_abort
# ---------------------------------------------------------------------------


def test_abort_zeroes_pii():
    import base64
    result = handle_abort(BASE_BODY, SHORTLIST_LABELS, None)
    encrypted = get_field(result.new_body, "encrypted_pii")
    decoded = base64.b64decode(encrypted)
    assert all(b == 0 for b in decoded)


def test_abort_sets_completed_state():
    result = handle_abort(BASE_BODY, SHORTLIST_LABELS, None)
    assert current_state(result.new_labels) == State.COMPLETED


def test_abort_removes_hitl_labels():
    labels = ["flow:buy", "state:shortlist_review", "hitl:review_shortlist"]
    result = handle_abort(BASE_BODY, labels, None)
    assert not any(l.startswith("hitl:") for l in result.new_labels)


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def test_dispatch_approve():
    result = dispatch("/approve", BASE_BODY, OFFER_DRAFT_LABELS)
    assert result is not None
    assert current_state(result.new_labels) == State.OFFER_SUBMITTED


def test_dispatch_unknown_command_raises():
    with pytest.raises(UnknownCommandError, match="unknown_cmd"):
        dispatch("/unknown_cmd", BASE_BODY, DISCOVER_LABELS)


def test_dispatch_non_command_returns_none():
    result = dispatch("Just a regular comment", BASE_BODY, DISCOVER_LABELS)
    assert result is None
