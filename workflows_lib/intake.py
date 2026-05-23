"""
Intake workflow step.

Receives a raw intake payload (from repository_dispatch or a directly-opened
issue), extracts structured requirements using the LLM, validates against the
rules YAML, encrypts PII, writes the structured front-matter to the issue, and
transitions it to state:discover.

The LLM is used here only to extract structure from free text. All validation
(budget range, income cap, field completeness) is deterministic.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from engine.crypto import encrypt_pii
from engine.extractor import ExtractionError, extract
from engine.schemas import BuyIntakeExtraction, RentIntakeExtraction
from engine.state_machine import State, flow_label, transition
from workflows_lib.issue_io import build_initial_body, new_workflow_front_matter, parse_front_matter

_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts"
_RULES_DIR = Path(__file__).parent.parent / "rules"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


def _generate_workflow_id(workflow_type: str) -> str:
    year = datetime.now(timezone.utc).year
    suffix = secrets.randbelow(900_000) + 100_000
    prefix = "rwa" if workflow_type == "buy" else "rwr"
    return f"{prefix}-{year}-{suffix}"


def _pii_dict_buy(extraction: BuyIntakeExtraction) -> dict[str, Any]:
    return {
        "full_name": extraction.full_name,
        "email": extraction.email,
        "phone": extraction.phone,
        "gross_monthly_income": extraction.gross_monthly_income,
        "deposit_available": extraction.deposit_available,
        "first_time_buyer": extraction.first_time_buyer,
    }


def _pii_dict_rent(extraction: RentIntakeExtraction) -> dict[str, Any]:
    return {
        "full_name": extraction.full_name,
        "email": extraction.email,
        "phone": extraction.phone,
        "gross_monthly_income": extraction.gross_monthly_income,
        "furnished_preference": extraction.furnished_preference,
        "pets": extraction.pets,
    }


def _requirements_buy(extraction: BuyIntakeExtraction) -> dict[str, Any]:
    return {
        "budget_min": extraction.budget_min,
        "budget_max": extraction.budget_max,
        "locations": extraction.locations,
        "bedrooms_min": extraction.bedrooms_min,
        "property_types": extraction.property_types,
        "must_haves": extraction.must_haves,
        "nice_to_haves": extraction.nice_to_haves,
        "move_in_by": str(extraction.move_in_by) if extraction.move_in_by else None,
    }


def _requirements_rent(extraction: RentIntakeExtraction) -> dict[str, Any]:
    return {
        "rent_min": extraction.rent_min,
        "rent_max": extraction.rent_max,
        "locations": extraction.locations,
        "bedrooms_min": extraction.bedrooms_min,
        "property_types": extraction.property_types,
        "must_haves": extraction.must_haves,
        "nice_to_haves": extraction.nice_to_haves,
        "move_in_by": str(extraction.move_in_by) if extraction.move_in_by else None,
    }


def process_intake(
    intake_text: str,
    workflow_type: str,
    *,
    encryption_key: bytes | None = None,
) -> tuple[str, list[str], int]:
    """
    Process a raw intake submission.

    Returns (issue_body, labels, tokens_used).
    Raises ExtractionError when the LLM output fails validation.
    Raises ValueError when intake_text is empty or workflow_type is invalid.
    """
    if not intake_text.strip():
        raise ValueError("intake_text is empty")
    if workflow_type not in ("buy", "rent"):
        raise ValueError(f"Unknown workflow_type: {workflow_type!r}")

    # --- LLM extraction ---
    if workflow_type == "buy":
        prompt_template = _load_prompt("intake_extract_v1.md")
        schema = BuyIntakeExtraction
    else:
        prompt_template = _load_prompt("rent_intake_extract_v1.md")
        schema = RentIntakeExtraction

    prompt = prompt_template.replace("{intake_text}", intake_text)
    extraction, tokens = extract(prompt, schema)

    # --- Build non-PII requirements ---
    if workflow_type == "buy":
        requirements = _requirements_buy(extraction)
        pii_data = _pii_dict_buy(extraction)
        jurisdiction = extraction.jurisdiction
    else:
        requirements = _requirements_rent(extraction)
        pii_data = _pii_dict_rent(extraction)
        jurisdiction = extraction.jurisdiction

    # --- Encrypt PII ---
    encrypted = encrypt_pii(json.dumps(pii_data), key=encryption_key)

    # --- Build front-matter ---
    workflow_id = _generate_workflow_id(workflow_type)
    fm = new_workflow_front_matter(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        jurisdiction=jurisdiction,
        requirements=requirements,
        encrypted_pii=encrypted,
    )
    fm["token_usage"] = tokens

    body = build_initial_body(fm)

    # --- Labels: start at intake, immediately advance to discover ---
    initial_labels = ["flow:" + workflow_type, State.INTAKE.value]
    new_labels = transition(initial_labels, State.DISCOVER)

    return body, new_labels, tokens
