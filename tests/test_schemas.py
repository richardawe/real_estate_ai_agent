import pytest
from pydantic import ValidationError

from engine.schemas import (
    BuyIntakeExtraction,
    InspectionSummary,
    OfferResponse,
    PropertyFitRationale,
    PropertyListing,
    RentIntakeExtraction,
)


# ---------------------------------------------------------------------------
# BuyIntakeExtraction
# ---------------------------------------------------------------------------

VALID_BUY = {
    "full_name": "Alice Smith",
    "email": "alice@example.com",
    "jurisdiction": "england",
    "budget_min": 300_000,
    "budget_max": 450_000,
    "locations": ["Reading"],
    "bedrooms_min": 3,
    "property_types": ["house"],
    "must_haves": ["garden"],
    "nice_to_haves": [],
    "first_time_buyer": True,
}


def test_buy_intake_valid():
    m = BuyIntakeExtraction(**VALID_BUY)
    assert m.budget_max == 450_000
    assert m.first_time_buyer is True


def test_buy_intake_max_below_min_raises():
    data = {**VALID_BUY, "budget_min": 450_000, "budget_max": 300_000}
    with pytest.raises(ValidationError, match="budget_max"):
        BuyIntakeExtraction(**data)


def test_buy_intake_invalid_email_raises():
    data = {**VALID_BUY, "email": "not-an-email"}
    with pytest.raises(ValidationError):
        BuyIntakeExtraction(**data)


def test_buy_intake_optional_fields_default():
    m = BuyIntakeExtraction(**VALID_BUY)
    assert m.phone is None
    assert m.move_in_by is None
    assert m.gross_monthly_income is None


# ---------------------------------------------------------------------------
# RentIntakeExtraction
# ---------------------------------------------------------------------------

VALID_RENT = {
    "full_name": "Bob Jones",
    "email": "bob@example.com",
    "jurisdiction": "england",
    "rent_max": 1_800,
    "locations": ["London"],
    "bedrooms_min": 1,
}


def test_rent_intake_valid():
    m = RentIntakeExtraction(**VALID_RENT)
    assert m.rent_min == 0
    assert m.pets is False


def test_rent_intake_missing_location_raises():
    data = {**VALID_RENT, "locations": []}
    with pytest.raises(ValidationError):
        RentIntakeExtraction(**data)


# ---------------------------------------------------------------------------
# PropertyListing
# ---------------------------------------------------------------------------


def test_property_listing_buy():
    m = PropertyListing(
        source_id="zoopla",
        external_id="z-123",
        title="3 bed house",
        price=400_000,
        address="42 Elm St",
        beds=3,
        url="https://example.com/listing/z-123",
    )
    assert m.beds == 3
    assert m.features == []


def test_property_listing_rent():
    m = PropertyListing(
        source_id="rightmove",
        external_id="rm-456",
        title="2 bed flat",
        rent_monthly=1_500,
        address="10 Oak Lane",
        beds=2,
        url="https://example.com/listing/rm-456",
    )
    assert m.rent_monthly == 1_500


# ---------------------------------------------------------------------------
# OfferResponse
# ---------------------------------------------------------------------------


def test_offer_accepted():
    m = OfferResponse(decision="accepted")
    assert m.counter_price is None


def test_offer_countered():
    m = OfferResponse(decision="countered", counter_price=395_000)
    assert m.counter_price == 395_000


def test_offer_invalid_decision_raises():
    with pytest.raises(ValidationError):
        OfferResponse(decision="maybe")


# ---------------------------------------------------------------------------
# InspectionSummary
# ---------------------------------------------------------------------------


def test_inspection_good():
    m = InspectionSummary(overall_condition="good")
    assert m.specialist_review_required is False


def test_inspection_invalid_condition_raises():
    with pytest.raises(ValidationError):
        InspectionSummary(overall_condition="excellent")


# ---------------------------------------------------------------------------
# PropertyFitRationale
# ---------------------------------------------------------------------------


def test_fit_rationale_valid():
    m = PropertyFitRationale(
        property_id="z-123",
        headline="Spacious house with garden in Reading",
        strengths=["Has garden", "In budget"],
        fit_summary="A solid match for your requirements.",
    )
    assert len(m.strengths) >= 1


def test_fit_rationale_headline_too_long_raises():
    with pytest.raises(ValidationError):
        PropertyFitRationale(
            property_id="z-123",
            headline="X" * 121,
            strengths=["ok"],
            fit_summary="fine",
        )
