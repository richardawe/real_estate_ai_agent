"""
Rental application orchestration (rent path).

After the user selects a property (state:viewings → state:shortlist_review
transition resolved), the agent:
1. Posts a rental application checklist from renting_v1.yaml.
2. Checks for fraud signals using the deterministic engine.
3. Waits for the user to upload documents and confirm.
4. Posts the hitl:landlord_decision task when confirmation arrives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_RULES_DIR = Path(__file__).parent.parent / "rules"


def _load_rent_rules() -> dict[str, Any]:
    with (_RULES_DIR / "renting_v1.yaml").open() as f:
        return yaml.safe_load(f)


def application_checklist_comment(listing: dict[str, Any]) -> str:
    """
    Generate an application checklist comment. Items from renting_v1.yaml.
    """
    rules = _load_rent_rules()
    docs = rules.get("required_application_docs", [])
    checklist = "\n".join(
        f"- [ ] {d.replace('_', ' ').title()}" for d in docs
    )

    return (
        "## Rental application checklist\n\n"
        f"**Property:** {listing.get('address', 'the selected property')}\n\n"
        "Please gather the following documents and upload them as issue attachments "
        "or note where you've sent them. Reply `/approve` when ready to submit.\n\n"
        + checklist
        + "\n\n"
        "The agent will not contact the landlord until you reply `/approve`."
    )


def check_fraud_signals(listing: dict[str, Any], market_median_rent: float | None) -> list[str]:
    """
    Check a listing for fraud signals defined in renting_v1.yaml.
    Returns a list of warning strings (empty if no signals).
    """
    rules = _load_rent_rules()
    signals = rules.get("fraud_signals", [])
    warnings: list[str] = []

    rent = listing.get("rent_monthly", 0) or 0

    for sig in signals:
        name = sig.get("signal", "")
        if name == "listing_price_below_market_pct" and market_median_rent:
            threshold_pct = sig["threshold"] / 100
            if rent < market_median_rent * (1 - threshold_pct):
                warnings.append(
                    f"Listing rent (£{rent:,}) is more than {sig['threshold']}% below "
                    f"local median (£{market_median_rent:,.0f}). Possible fraud."
                )
        elif name == "no_in_person_viewing_offered" and sig.get("value"):
            if listing.get("viewing_online_only"):
                warnings.append("Listing offers online-only viewings — no in-person visits.")
        elif name == "upfront_payment_demanded_before_lease" and sig.get("value"):
            if listing.get("upfront_payment_required"):
                warnings.append(
                    "Listing demands upfront payment before signing a lease. "
                    "This is a common fraud pattern."
                )

    return warnings
