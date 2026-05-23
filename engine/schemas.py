"""
Pydantic schemas for all structured LLM outputs.

Every LLM response that becomes structured data must be validated against
one of these models before it is acted on. The LLM is not trusted to produce
correct data; validation failure raises ExtractionError, which the caller
surfaces as a comment asking the user to clarify.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Intake extraction
# ---------------------------------------------------------------------------


class BuyIntakeExtraction(BaseModel):
    """Structured requirements extracted from a buying intake form submission."""

    full_name: str = Field(min_length=1)
    email: str = Field(pattern=r".+@.+\..+")
    phone: Optional[str] = None
    jurisdiction: str = Field(min_length=2)
    budget_min: int = Field(gt=0)
    budget_max: int = Field(gt=0)
    locations: list[str] = Field(min_length=1)
    bedrooms_min: int = Field(ge=1)
    property_types: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    move_in_by: Optional[date] = None
    gross_monthly_income: Optional[int] = None
    deposit_available: Optional[int] = None
    first_time_buyer: bool = False

    @field_validator("budget_max")
    @classmethod
    def max_exceeds_min(cls, v: int, info: Any) -> int:
        min_val = info.data.get("budget_min", 0)
        if v < min_val:
            raise ValueError("budget_max must be >= budget_min")
        return v


class RentIntakeExtraction(BaseModel):
    """Structured requirements extracted from a renting intake form submission."""

    full_name: str = Field(min_length=1)
    email: str = Field(pattern=r".+@.+\..+")
    phone: Optional[str] = None
    jurisdiction: str = Field(min_length=2)
    rent_max: int = Field(gt=0)
    rent_min: int = Field(default=0, ge=0)
    locations: list[str] = Field(min_length=1)
    bedrooms_min: int = Field(ge=1)
    property_types: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    move_in_by: Optional[date] = None
    gross_monthly_income: Optional[int] = None
    furnished_preference: Optional[str] = None  # "furnished", "unfurnished", "either"
    pets: bool = False


# ---------------------------------------------------------------------------
# Property listing extraction
# ---------------------------------------------------------------------------


class PropertyListing(BaseModel):
    """A single property extracted from a listing page."""

    source_id: str
    external_id: str
    title: str
    price: Optional[int] = None           # buy price or None for rent
    rent_monthly: Optional[int] = None    # rent or None for buy
    address: str
    location_slug: Optional[str] = None
    beds: int = Field(ge=0)
    property_type: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    url: str
    description_snippet: Optional[str] = None


# ---------------------------------------------------------------------------
# Offer parsing (inbound email from seller / agent)
# ---------------------------------------------------------------------------


class OfferResponse(BaseModel):
    """Parsed seller response to a submitted offer."""

    decision: str = Field(pattern=r"^(accepted|rejected|countered)$")
    counter_price: Optional[int] = None     # set when decision == "countered"
    counter_notes: Optional[str] = None
    conditions: list[str] = Field(default_factory=list)
    responding_party: Optional[str] = None


# ---------------------------------------------------------------------------
# Inspection report summary
# ---------------------------------------------------------------------------


class InspectionSummary(BaseModel):
    """Key findings extracted from an inspection report."""

    overall_condition: str = Field(pattern=r"^(good|fair|poor)$")
    critical_issues: list[str] = Field(default_factory=list)
    recommended_repairs: list[str] = Field(default_factory=list)
    estimated_repair_cost_min: Optional[int] = None
    estimated_repair_cost_max: Optional[int] = None
    specialist_review_required: bool = False


# ---------------------------------------------------------------------------
# Fit rationale (shortlist comment)
# ---------------------------------------------------------------------------


class PropertyFitRationale(BaseModel):
    """One-paragraph rationale for including a property in the shortlist."""

    property_id: str
    headline: str = Field(max_length=120)
    strengths: list[str] = Field(min_length=1)
    weaknesses: list[str] = Field(default_factory=list)
    fit_summary: str = Field(max_length=400)
