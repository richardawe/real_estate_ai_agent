"""
Deterministic affordability and property-scoring calculations.

All thresholds and weights come from rules YAML files. This module never
embeds numeric constants — load them from rules via load_rules() or pass them
in directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_RULES_DIR = Path(__file__).parent.parent / "rules"


def _load_rules(filename: str) -> dict[str, Any]:
    with (_RULES_DIR / filename).open() as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Buying affordability
# ---------------------------------------------------------------------------


def monthly_mortgage_payment(
    principal: float,
    annual_rate_pct: float,
    term_years: int,
) -> float:
    """Standard fixed-rate monthly mortgage payment (P&I)."""
    r = annual_rate_pct / 100 / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def is_affordable_buy(
    price: float,
    gross_monthly_income: float,
    deposit: float,
    rules: dict[str, Any] | None = None,
) -> tuple[bool, float]:
    """
    Return (affordable, monthly_payment).
    Affordable when the monthly payment is within the income fraction cap
    defined in rules.
    """
    if rules is None:
        rules = _load_rules("buying_v1.yaml")
    aff = rules["affordability"]
    rate = aff["default_interest_rate_pct"]
    term = aff["default_term_years"]
    cap_pct = aff["max_monthly_payment_pct_of_income"]

    principal = max(0.0, price - deposit)
    payment = monthly_mortgage_payment(principal, rate, term)
    affordable = payment <= gross_monthly_income * cap_pct
    return affordable, payment


def stamp_duty(
    price: float,
    jurisdiction_rules: dict[str, Any],
    first_time_buyer: bool = False,
) -> float:
    """
    Calculate stamp duty / transfer tax for a jurisdiction.
    Expects jurisdiction rules with an 'overlays.buying.stamp_duty_thresholds' key.
    Returns 0.0 when no thresholds are defined for the jurisdiction.
    """
    buying = jurisdiction_rules.get("overlays", {}).get("buying", {})
    thresholds = buying.get("stamp_duty_thresholds")
    if not thresholds:
        return 0.0

    ftb = buying.get("first_time_buyer_relief", {}) if first_time_buyer else {}
    zero_rate_threshold = ftb.get("zero_rate_threshold", 0)
    relief_cap = ftb.get("relief_cap", 0)

    if first_time_buyer and price <= relief_cap and relief_cap > 0:
        # FTB relief applies: 0% up to zero_rate_threshold, 5% above up to cap.
        if price <= zero_rate_threshold:
            return 0.0
        return (price - zero_rate_threshold) * 0.05

    # Standard banded calculation.
    total = 0.0
    prev_threshold = 0.0
    for band in thresholds:
        band_ceiling = band["up_to"]
        rate = band["rate"]
        if band_ceiling is None:
            taxable = price - prev_threshold
        else:
            taxable = min(price, band_ceiling) - prev_threshold
        if taxable > 0:
            total += taxable * rate
        if band_ceiling is None or price <= band_ceiling:
            break
        prev_threshold = band_ceiling
    return round(total, 2)


# ---------------------------------------------------------------------------
# Renting affordability
# ---------------------------------------------------------------------------


def is_affordable_rent(
    rent_monthly: float,
    gross_monthly_income: float,
    rules: dict[str, Any] | None = None,
) -> tuple[bool, float]:
    """
    Return (affordable, rent_to_income_ratio).
    Affordable when rent is within the fraction cap defined in rules.
    """
    if rules is None:
        rules = _load_rules("renting_v1.yaml")
    cap_pct = rules["affordability"]["max_rent_pct_of_gross_income"]
    ratio = rent_monthly / gross_monthly_income if gross_monthly_income else math.inf
    return ratio <= cap_pct, ratio


# ---------------------------------------------------------------------------
# Property scoring
# ---------------------------------------------------------------------------


@dataclass
class PropertyScore:
    total: float
    price_fit: float
    location_fit: float
    size_fit: float
    must_haves_hit: float
    nice_to_haves_hit: float


def score_property(
    prop: dict[str, Any],
    requirements: dict[str, Any],
    must_have_score: float,
    matching_rules: dict[str, Any] | None = None,
    workflow_rules: dict[str, Any] | None = None,
) -> PropertyScore:
    """
    Score a property against requirements. Returns a PropertyScore with
    component scores and a weighted total (0.0–1.0).

    prop keys used: price (or rent_monthly), beds, location_score (pre-computed
    0.0–1.0 from caller), features.
    workflow_rules is the buy/rent rules dict supplying scoring_weights.
    """
    if matching_rules is None:
        matching_rules = _load_rules("matching_v1.yaml")
    if workflow_rules is None:
        raise ValueError("workflow_rules must be provided")

    weights: dict[str, float] = workflow_rules["scoring_weights"]

    # --- price fit ---
    budget_min = requirements.get("budget_min") or requirements.get("rent_min", 0)
    budget_max = requirements.get("budget_max") or requirements.get("rent_max", 0)
    prop_price = prop.get("price") or prop.get("rent_monthly", 0)
    midpoint = (budget_min + budget_max) / 2 if budget_max else prop_price
    decay = matching_rules["price_fit_decay"]
    if midpoint > 0:
        deviation = abs(prop_price - midpoint) / midpoint
        price_fit = max(0.0, 1.0 - deviation / decay)
    else:
        price_fit = 1.0

    # --- location fit --- (caller pre-computes; fall back to 0 if absent)
    location_fit: float = prop.get("location_score", 0.0)

    # --- size fit ---
    required_beds = requirements.get("bedrooms_min", 1)
    actual_beds = prop.get("beds", 0)
    size_fit = min(1.0, actual_beds / required_beds) if required_beds else 1.0
    extra = max(0, actual_beds - required_beds)
    bonus_per = matching_rules["size_extra_bed_bonus"]
    cap = matching_rules["size_extra_bed_bonus_cap"]
    size_fit = min(1.0, size_fit + min(extra * bonus_per, cap))

    # --- nice-to-haves ---
    nice_to_haves: list[str] = requirements.get("nice_to_haves", [])
    prop_features: list[str] = prop.get("features", [])
    nth_score = (
        sum(1 for n in nice_to_haves if n in prop_features) / len(nice_to_haves)
        if nice_to_haves
        else 1.0
    )

    total = (
        weights["price_fit"] * price_fit
        + weights["location_fit"] * location_fit
        + weights["size_fit"] * size_fit
        + weights["must_haves_hit"] * must_have_score
        + weights["nice_to_haves_hit"] * nth_score
    )

    return PropertyScore(
        total=round(total, 4),
        price_fit=round(price_fit, 4),
        location_fit=round(location_fit, 4),
        size_fit=round(size_fit, 4),
        must_haves_hit=round(must_have_score, 4),
        nice_to_haves_hit=round(nth_score, 4),
    )
