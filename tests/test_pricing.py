import pytest
import yaml
from pathlib import Path

from engine.pricing import (
    is_affordable_buy,
    is_affordable_rent,
    monthly_mortgage_payment,
    score_property,
    stamp_duty,
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
def matching_rules():
    with (RULES_DIR / "matching_v1.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def england_rules():
    with (RULES_DIR / "jurisdictions" / "england_v1.yaml").open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# monthly_mortgage_payment
# ---------------------------------------------------------------------------


def test_mortgage_payment_known_value():
    # £300k at 6.5% over 25 years. Expected ~£2,028/month.
    payment = monthly_mortgage_payment(300_000, 6.5, 25)
    assert 2_000 <= payment <= 2_100


def test_mortgage_payment_zero_rate():
    payment = monthly_mortgage_payment(300_000, 0, 25)
    assert payment == pytest.approx(300_000 / 300, rel=1e-6)


# ---------------------------------------------------------------------------
# is_affordable_buy
# ---------------------------------------------------------------------------


def test_affordable_buy(buy_rules):
    # £200k price, £50k deposit → £150k loan.
    # At 6.5%, 25 years ≈ £1,014/month. £5k/month income → well within 28%.
    affordable, payment = is_affordable_buy(200_000, 5_000, 50_000, rules=buy_rules)
    assert affordable is True
    assert 900 < payment < 1_200


def test_unaffordable_buy(buy_rules):
    # £500k price, £0 deposit → £500k loan.
    # At 6.5%, 25 years ≈ £3,380/month. £5k/month income → 67.6% > 28%.
    affordable, payment = is_affordable_buy(500_000, 5_000, 0, rules=buy_rules)
    assert affordable is False


def test_affordable_buy_with_large_deposit(buy_rules):
    # £500k price, £400k deposit → £100k loan ≈ £676/month. Affordable.
    affordable, _ = is_affordable_buy(500_000, 5_000, 400_000, rules=buy_rules)
    assert affordable is True


# ---------------------------------------------------------------------------
# stamp_duty (England)
# ---------------------------------------------------------------------------


def test_stamp_duty_below_threshold(england_rules):
    assert stamp_duty(200_000, england_rules) == 0.0


def test_stamp_duty_at_250k_boundary(england_rules):
    assert stamp_duty(250_000, england_rules) == 0.0


def test_stamp_duty_above_threshold(england_rules):
    # £300k: 0% on first £250k, 5% on £50k = £2,500.
    assert stamp_duty(300_000, england_rules) == pytest.approx(2_500.0)


def test_stamp_duty_higher_band(england_rules):
    # £1m: 0% on £250k, 5% on £675k, 10% on £75k = 0 + 33,750 + 7,500 = £41,250.
    assert stamp_duty(1_000_000, england_rules) == pytest.approx(41_250.0)


def test_stamp_duty_ftb_below_zero_threshold(england_rules):
    assert stamp_duty(300_000, england_rules, first_time_buyer=True) == 0.0


def test_stamp_duty_ftb_above_zero_threshold(england_rules):
    # FTB, £500k: 0% on £425k, 5% on £75k = £3,750.
    assert stamp_duty(500_000, england_rules, first_time_buyer=True) == pytest.approx(3_750.0)


def test_stamp_duty_ftb_above_cap_uses_standard(england_rules):
    # £700k > £625k cap → FTB relief does not apply, use standard rates.
    sd_standard = stamp_duty(700_000, england_rules, first_time_buyer=False)
    sd_ftb = stamp_duty(700_000, england_rules, first_time_buyer=True)
    assert sd_ftb == sd_standard


# ---------------------------------------------------------------------------
# is_affordable_rent
# ---------------------------------------------------------------------------


def test_affordable_rent(rent_rules):
    affordable, ratio = is_affordable_rent(1_200, 5_000, rules=rent_rules)
    assert affordable is True
    assert ratio == pytest.approx(0.24, rel=1e-3)


def test_unaffordable_rent(rent_rules):
    affordable, ratio = is_affordable_rent(2_000, 5_000, rules=rent_rules)
    assert affordable is False
    assert ratio == pytest.approx(0.40, rel=1e-3)


def test_affordable_rent_at_boundary(rent_rules):
    # Exactly 30% of income.
    affordable, ratio = is_affordable_rent(1_500, 5_000, rules=rent_rules)
    assert affordable is True
    assert ratio == pytest.approx(0.30, rel=1e-3)


# ---------------------------------------------------------------------------
# score_property
# ---------------------------------------------------------------------------


@pytest.fixture
def buy_requirements():
    return {
        "budget_min": 300_000,
        "budget_max": 500_000,
        "bedrooms_min": 3,
        "must_haves": ["garden"],
        "nice_to_haves": ["garage"],
    }


def test_score_perfect_property(buy_rules, matching_rules, buy_requirements):
    prop = {
        "price": 400_000,   # midpoint
        "beds": 3,
        "location_score": 1.0,
        "features": ["garden", "garage"],
    }
    s = score_property(prop, buy_requirements, must_have_score=1.0,
                       matching_rules=matching_rules, workflow_rules=buy_rules)
    assert s.total == pytest.approx(1.0, rel=1e-2)
    assert s.price_fit == pytest.approx(1.0, rel=1e-2)


def test_score_poor_location(buy_rules, matching_rules, buy_requirements):
    prop = {
        "price": 400_000,
        "beds": 3,
        "location_score": 0.0,
        "features": ["garden", "garage"],
    }
    s = score_property(prop, buy_requirements, must_have_score=1.0,
                       matching_rules=matching_rules, workflow_rules=buy_rules)
    assert s.location_fit == 0.0
    assert s.total < 1.0


def test_score_extra_beds_bonus(buy_rules, matching_rules, buy_requirements):
    # required = 3 beds. A property with fewer beds must score lower.
    prop_under = {"price": 400_000, "beds": 2, "location_score": 1.0, "features": ["garden", "garage"]}
    prop_exact = {"price": 400_000, "beds": 3, "location_score": 1.0, "features": ["garden", "garage"]}
    s_under = score_property(prop_under, buy_requirements, must_have_score=1.0,
                             matching_rules=matching_rules, workflow_rules=buy_rules)
    s_exact = score_property(prop_exact, buy_requirements, must_have_score=1.0,
                             matching_rules=matching_rules, workflow_rules=buy_rules)
    assert s_exact.size_fit > s_under.size_fit
    assert s_exact.size_fit == pytest.approx(1.0)


def test_score_no_workflow_rules_raises(matching_rules, buy_requirements):
    prop = {"price": 400_000, "beds": 3, "location_score": 1.0, "features": []}
    with pytest.raises(ValueError, match="workflow_rules"):
        score_property(prop, buy_requirements, must_have_score=1.0,
                       matching_rules=matching_rules, workflow_rules=None)
