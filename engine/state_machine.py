"""
Workflow state machine driven entirely by GitHub Issue labels.

State is encoded as a single label with the prefix "state:". All mutations
go through transition(); nothing else should add or remove state labels.
HITL tasks are encoded as "hitl:<kind>" labels and are orthogonal to state.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class State(str, Enum):
    INTAKE = "state:intake"
    DISCOVER = "state:discover"
    SHORTLIST_REVIEW = "state:shortlist_review"
    VIEWINGS = "state:viewings"
    OFFER_DRAFT = "state:offer_draft"
    OFFER_SUBMITTED = "state:offer_submitted"
    DUE_DILIGENCE = "state:due_diligence"
    LEASE_REVIEW = "state:lease_review"
    CLOSING = "state:closing"
    COMPLETED = "state:completed"


_STATE_VALUES: frozenset[str] = frozenset(s.value for s in State)

# Every permitted (from → to) pair. Anything not listed is forbidden.
_ALLOWED_TRANSITIONS: frozenset[tuple[State, State]] = frozenset(
    {
        # Buy path
        (State.INTAKE, State.DISCOVER),
        (State.DISCOVER, State.SHORTLIST_REVIEW),
        (State.SHORTLIST_REVIEW, State.VIEWINGS),
        (State.VIEWINGS, State.OFFER_DRAFT),
        (State.OFFER_DRAFT, State.OFFER_SUBMITTED),
        (State.OFFER_SUBMITTED, State.DUE_DILIGENCE),
        (State.DUE_DILIGENCE, State.CLOSING),
        # Rent path diverges here
        (State.SHORTLIST_REVIEW, State.LEASE_REVIEW),
        (State.LEASE_REVIEW, State.CLOSING),
        # Shared terminal
        (State.CLOSING, State.COMPLETED),
    }
)


class InvalidTransitionError(Exception):
    pass


def current_state(labels: list[str]) -> Optional[State]:
    """Return the single state label from the list, or None if absent."""
    matches = [l for l in labels if l in _STATE_VALUES]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"Multiple state labels present: {matches}")
    return State(matches[0])


def transition(labels: list[str], to_state: State) -> list[str]:
    """
    Return a new label list with the state label replaced by to_state.
    Raises InvalidTransitionError when the move is not permitted.
    """
    from_state = current_state(labels)
    if from_state is None:
        raise InvalidTransitionError("No state label found on issue")
    if (from_state, to_state) not in _ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(
            f"Transition {from_state.value!r} → {to_state.value!r} is not allowed"
        )
    stripped = [l for l in labels if l not in _STATE_VALUES]
    return stripped + [to_state.value]


def add_hitl(labels: list[str], kind: str) -> list[str]:
    """Add a hitl:<kind> label; idempotent."""
    label = f"hitl:{kind}"
    return labels if label in labels else labels + [label]


def remove_hitl(labels: list[str], kind: str) -> list[str]:
    """Remove a hitl:<kind> label if present."""
    return [l for l in labels if l != f"hitl:{kind}"]


def has_hitl(labels: list[str], kind: str) -> bool:
    return f"hitl:{kind}" in labels


def flow_label(workflow_type: str) -> str:
    """Return the canonical flow label for a workflow type ('buy' or 'rent')."""
    if workflow_type not in ("buy", "rent"):
        raise ValueError(f"Unknown workflow type: {workflow_type!r}")
    return f"flow:{workflow_type}"
