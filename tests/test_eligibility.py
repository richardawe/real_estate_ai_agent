import pytest
import yaml
from pathlib import Path

from engine.eligibility import (
    EligibilityResult,
    FilterResult,
    check_hard_filters,
    is_eligible,
    must_have_score,
)

RULES_DIR = Path(__file__).parent.parent / "rules"


@pytest.fixture
def buy_rules():
    with (RULES_DIR / "buying_v1.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def rent_rules():
    with (RULES_DIR / "renting_v1.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def buy_requirements():
    return {
        "budget_min": 300_000,
        "budget_max": 450_000,
        "bedrooms_min": 3,
        "property_types": ["house", "semi"],
        "must_haves": ["garden", "parking"],
    }


@pytest.fixture
def rent_requirements():
    return {
        "rent_min": 1_000,
        "rent_max": 2_000,
        "bedrooms_min": 2,
        "must_haves": ["parking"],
    }


# ---------------------------------------------------------------------------
# check_hard_filters — buy
# ---------------------------------------------------------------------------


def test_buy_price_in_range_passes(buy_rules, buy_requirements):
    prop = {"price": 400_000, "beds": 3, "property_type": "house", "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    assert all(r.passed for r in results)


def test_buy_price_below_min_fails(buy_rules, buy_requirements):
    prop = {"price": 200_000, "beds": 3, "property_type": "house", "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    failed = [r for r in results if not r.passed]
    assert len(failed) >= 1
    assert any("budget_min" in r.reason or "< min" in r.reason for r in failed)


def test_buy_price_above_max_fails(buy_rules, buy_requirements):
    prop = {"price": 500_000, "beds": 3, "property_type": "house", "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    failed = [r for r in results if not r.passed]
    assert any("> max" in r.reason for r in failed)


def test_buy_too_few_beds_fails(buy_rules, buy_requirements):
    prop = {"price": 380_000, "beds": 2, "property_type": "house", "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    failed = [r for r in results if not r.passed]
    assert any("beds" in r.reason for r in failed)


def test_buy_wrong_property_type_fails(buy_rules, buy_requirements):
    prop = {"price": 380_000, "beds": 3, "property_type": "flat", "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    failed = [r for r in results if not r.passed]
    assert any("property_type" in r.reason for r in failed)


def test_buy_missing_optional_field_ok(buy_rules, buy_requirements):
    # property_type missing — it's marked optional in the rules
    prop = {"price": 380_000, "beds": 3, "features": []}
    results = check_hard_filters(prop, buy_requirements, buy_rules)
    # Should not fail on property_type
    failed = [r for r in results if not r.passed]
    assert not any("property_type" in r.reason for r in failed)


# ---------------------------------------------------------------------------
# must_have_score
# ---------------------------------------------------------------------------


def test_must_have_all_present():
    req = {"must_haves": ["garden", "parking"]}
    prop = {"features": ["garden", "parking", "garage"]}
    assert must_have_score(prop, req) == 1.0


def test_must_have_partial():
    req = {"must_haves": ["garden", "parking"]}
    prop = {"features": ["garden"]}
    assert must_have_score(prop, req) == 0.5


def test_must_have_none_required():
    req = {"must_haves": []}
    prop = {"features": []}
    assert must_have_score(prop, req) == 1.0


def test_must_have_none_present():
    req = {"must_haves": ["garden", "parking"]}
    prop = {"features": []}
    assert must_have_score(prop, req) == 0.0


# ---------------------------------------------------------------------------
# is_eligible — buy
# ---------------------------------------------------------------------------


def test_eligible_property_buy(buy_requirements):
    prop = {
        "price": 400_000,
        "beds": 3,
        "property_type": "house",
        "features": ["garden", "parking"],
    }
    result = is_eligible(prop, buy_requirements, "buy")
    assert result.eligible is True
    assert result.failed_filters == []
    assert result.must_have_score == 1.0


def test_ineligible_missing_must_have_buy(buy_requirements):
    prop = {
        "price": 400_000,
        "beds": 3,
        "property_type": "house",
        "features": ["garden"],  # missing parking
    }
    result = is_eligible(prop, buy_requirements, "buy")
    assert result.eligible is False
    assert result.must_have_score == 0.5


def test_ineligible_failed_hard_filter_buy(buy_requirements):
    prop = {
        "price": 600_000,  # over budget
        "beds": 3,
        "property_type": "house",
        "features": ["garden", "parking"],
    }
    result = is_eligible(prop, buy_requirements, "buy")
    assert result.eligible is False
    assert len(result.failed_filters) >= 1


# ---------------------------------------------------------------------------
# is_eligible — rent
# ---------------------------------------------------------------------------


def test_eligible_property_rent(rent_requirements):
    prop = {"rent_monthly": 1_500, "beds": 2, "features": ["parking"]}
    result = is_eligible(prop, rent_requirements, "rent")
    assert result.eligible is True


def test_ineligible_rent_too_expensive(rent_requirements):
    prop = {"rent_monthly": 2_500, "beds": 2, "features": ["parking"]}
    result = is_eligible(prop, rent_requirements, "rent")
    assert result.eligible is False
