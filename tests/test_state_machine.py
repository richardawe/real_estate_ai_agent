import pytest

from engine.state_machine import (
    State,
    InvalidTransitionError,
    add_hitl,
    current_state,
    flow_label,
    has_hitl,
    remove_hitl,
    transition,
)


# ---------------------------------------------------------------------------
# current_state
# ---------------------------------------------------------------------------


def test_current_state_found():
    labels = ["flow:buy", "state:intake", "hitl:review_shortlist"]
    assert current_state(labels) == State.INTAKE


def test_current_state_none_when_absent():
    assert current_state(["flow:buy", "hitl:approve_offer"]) is None


def test_current_state_raises_on_multiple():
    with pytest.raises(ValueError, match="Multiple state labels"):
        current_state(["state:intake", "state:discover"])


# ---------------------------------------------------------------------------
# transition — valid paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_state, to_state",
    [
        (State.INTAKE, State.DISCOVER),
        (State.DISCOVER, State.SHORTLIST_REVIEW),
        (State.SHORTLIST_REVIEW, State.VIEWINGS),
        (State.VIEWINGS, State.OFFER_DRAFT),
        (State.OFFER_DRAFT, State.OFFER_SUBMITTED),
        (State.OFFER_SUBMITTED, State.DUE_DILIGENCE),
        (State.DUE_DILIGENCE, State.CLOSING),
        # Rent path
        (State.SHORTLIST_REVIEW, State.LEASE_REVIEW),
        (State.LEASE_REVIEW, State.CLOSING),
        # Terminal
        (State.CLOSING, State.COMPLETED),
    ],
)
def test_valid_transitions(from_state, to_state):
    labels = ["flow:buy", from_state.value]
    result = transition(labels, to_state)
    assert to_state.value in result
    assert from_state.value not in result
    assert "flow:buy" in result


def test_transition_preserves_hitl_labels():
    labels = ["flow:buy", "state:discover", "hitl:review_shortlist"]
    result = transition(labels, State.SHORTLIST_REVIEW)
    assert "hitl:review_shortlist" in result


# ---------------------------------------------------------------------------
# transition — invalid paths
# ---------------------------------------------------------------------------


def test_transition_skipping_states_raises():
    labels = ["state:intake"]
    with pytest.raises(InvalidTransitionError):
        transition(labels, State.COMPLETED)


def test_transition_backwards_raises():
    labels = ["state:discover"]
    with pytest.raises(InvalidTransitionError):
        transition(labels, State.INTAKE)


def test_transition_no_state_label_raises():
    with pytest.raises(InvalidTransitionError, match="No state label"):
        transition(["flow:buy"], State.DISCOVER)


# ---------------------------------------------------------------------------
# HITL label helpers
# ---------------------------------------------------------------------------


def test_add_hitl():
    labels = ["state:discover"]
    result = add_hitl(labels, "review_shortlist")
    assert "hitl:review_shortlist" in result


def test_add_hitl_idempotent():
    labels = ["state:discover"]
    labels = add_hitl(labels, "approve_offer")
    labels = add_hitl(labels, "approve_offer")
    assert labels.count("hitl:approve_offer") == 1


def test_remove_hitl():
    labels = ["state:discover", "hitl:review_shortlist"]
    result = remove_hitl(labels, "review_shortlist")
    assert "hitl:review_shortlist" not in result
    assert "state:discover" in result


def test_remove_hitl_noop_when_absent():
    labels = ["state:discover"]
    result = remove_hitl(labels, "review_shortlist")
    assert result == labels


def test_has_hitl_true():
    assert has_hitl(["state:discover", "hitl:approve_offer"], "approve_offer")


def test_has_hitl_false():
    assert not has_hitl(["state:discover"], "approve_offer")


# ---------------------------------------------------------------------------
# flow_label
# ---------------------------------------------------------------------------


def test_flow_label_buy():
    assert flow_label("buy") == "flow:buy"


def test_flow_label_rent():
    assert flow_label("rent") == "flow:rent"


def test_flow_label_invalid():
    with pytest.raises(ValueError, match="Unknown workflow type"):
        flow_label("sell")
