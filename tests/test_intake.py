"""Tests for the intake workflow step."""

import json
import pytest
from unittest.mock import patch

from engine.crypto import generate_key
from engine.extractor import ExtractionError
from engine.schemas import BuyIntakeExtraction, RentIntakeExtraction
from engine.state_machine import State, current_state
from workflows_lib.intake import process_intake
from workflows_lib.issue_io import get_field, parse_front_matter

VALID_BUY_EXTRACTION = BuyIntakeExtraction(
    full_name="Alice Smith",
    email="alice@example.com",
    jurisdiction="england",
    budget_min=300_000,
    budget_max=450_000,
    locations=["Reading"],
    bedrooms_min=3,
    property_types=["house"],
    must_haves=["garden"],
    nice_to_haves=[],
    first_time_buyer=False,
)

VALID_RENT_EXTRACTION = RentIntakeExtraction(
    full_name="Bob Jones",
    email="bob@example.com",
    jurisdiction="england",
    rent_min=1_000,
    rent_max=1_800,
    locations=["Bristol"],
    bedrooms_min=2,
)

FAKE_KEY = bytes.fromhex(generate_key())


def _mock_extract(extraction):
    """Return a side_effect that yields (extraction, tokens)."""
    return (extraction, 42)


@patch("workflows_lib.intake.extract", return_value=(VALID_BUY_EXTRACTION, 42))
def test_process_buy_intake_returns_correct_state(mock_extract):
    body, labels, tokens = process_intake(
        "I want to buy a 3-bed house in Reading for around £400k",
        "buy",
        encryption_key=FAKE_KEY,
    )
    assert current_state(labels) == State.DISCOVER
    assert "flow:buy" in labels
    assert tokens == 42


@patch("workflows_lib.intake.extract", return_value=(VALID_BUY_EXTRACTION, 10))
def test_process_buy_intake_front_matter_structure(mock_extract):
    body, labels, _ = process_intake("any text", "buy", encryption_key=FAKE_KEY)
    fm, _ = parse_front_matter(body)
    assert fm["type"] == "buy"
    assert fm["jurisdiction"] == "england"
    assert fm["requirements"]["budget_max"] == 450_000
    assert fm["requirements"]["locations"] == ["Reading"]
    assert fm["shortlist"] == []
    assert "encrypted_pii" in fm
    assert fm["encrypted_pii"] != ""


@patch("workflows_lib.intake.extract", return_value=(VALID_BUY_EXTRACTION, 10))
def test_pii_is_encrypted_not_plaintext(mock_extract):
    body, _, _ = process_intake("any text", "buy", encryption_key=FAKE_KEY)
    # Plaintext PII must not appear in the issue body.
    assert "Alice Smith" not in body
    assert "alice@example.com" not in body


@patch("workflows_lib.intake.extract", return_value=(VALID_BUY_EXTRACTION, 10))
def test_encrypted_pii_is_decryptable(mock_extract):
    from engine.crypto import decrypt_pii
    body, _, _ = process_intake("any text", "buy", encryption_key=FAKE_KEY)
    encrypted = get_field(body, "encrypted_pii")
    decrypted = json.loads(decrypt_pii(encrypted, key=FAKE_KEY))
    assert decrypted["full_name"] == "Alice Smith"
    assert decrypted["email"] == "alice@example.com"


@patch("workflows_lib.intake.extract", return_value=(VALID_RENT_EXTRACTION, 5))
def test_process_rent_intake(mock_extract):
    body, labels, _ = process_intake("rent a flat", "rent", encryption_key=FAKE_KEY)
    fm, _ = parse_front_matter(body)
    assert fm["type"] == "rent"
    assert "flow:rent" in labels
    assert current_state(labels) == State.DISCOVER


def test_empty_intake_text_raises():
    with pytest.raises(ValueError, match="empty"):
        process_intake("   ", "buy", encryption_key=FAKE_KEY)


def test_unknown_workflow_type_raises():
    with pytest.raises(ValueError, match="Unknown workflow_type"):
        process_intake("some text", "sell", encryption_key=FAKE_KEY)


@patch("workflows_lib.intake.extract", side_effect=ExtractionError("bad JSON"))
def test_extraction_failure_propagates(mock_extract):
    with pytest.raises(ExtractionError):
        process_intake("garbled text", "buy", encryption_key=FAKE_KEY)
