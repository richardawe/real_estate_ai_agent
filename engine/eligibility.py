"""
Deterministic property eligibility checking.

Evaluates whether a property passes the hard filters defined in a rules YAML,
and checks must-have feature matching. All thresholds come from the YAML —
never from embedded constants in this file.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_RULES_DIR = Path(__file__).parent.parent / "rules"

_OPS = {
    "gte": operator.ge,
    "lte": operator.le,
    "gt": operator.gt,
    "lt": operator.lt,
    "eq": operator.eq,
}


def _load_rules(workflow_type: str, version: str = "v1") -> dict[str, Any]:
    filename = f"{'buying' if workflow_type == 'buy' else 'renting'}_{version}.yaml"
    path = _RULES_DIR / filename
    with path.open() as fh:
        return yaml.safe_load(fh)


def _resolve_ref(ref: str, requirements: dict[str, Any]) -> Any:
    """Resolve a dot-path reference like 'requirements.budget_min'."""
    parts = ref.split(".")
    if parts[0] != "requirements":
        raise ValueError(f"Unknown reference root: {parts[0]!r}")
    value = requirements
    for part in parts[1:]:
        value = value[part]
    return value


@dataclass
class FilterResult:
    passed: bool
    reason: str


@dataclass
class EligibilityResult:
    eligible: bool
    failed_filters: list[FilterResult] = field(default_factory=list)
    must_have_score: float = 0.0


def check_hard_filters(
    prop: dict[str, Any],
    requirements: dict[str, Any],
    rules: dict[str, Any],
) -> list[FilterResult]:
    """Run every hard filter from the rules YAML against a property dict."""
    results: list[FilterResult] = []

    for filt in rules.get("hard_filters", []):
        field_name: str = filt["field"]
        op_name: str = filt["op"]
        optional: bool = filt.get("optional", False)

        prop_value = prop.get(field_name)
        if prop_value is None:
            if optional:
                continue
            results.append(FilterResult(False, f"Missing field {field_name!r}"))
            continue

        if op_name == "between":
            lo = _resolve_ref(filt["refs"][0], requirements)
            hi = _resolve_ref(filt["refs"][1], requirements)
            # lo or hi may be None (open-ended ranges)
            if lo is not None and prop_value < lo:
                results.append(
                    FilterResult(False, f"{field_name} {prop_value} < min {lo}")
                )
                continue
            if hi is not None and prop_value > hi:
                results.append(
                    FilterResult(False, f"{field_name} {prop_value} > max {hi}")
                )
                continue
            results.append(FilterResult(True, f"{field_name} in range"))

        elif op_name == "in":
            allowed = _resolve_ref(filt["ref"], requirements)
            if allowed and prop_value not in allowed:
                results.append(
                    FilterResult(False, f"{field_name} {prop_value!r} not in {allowed}")
                )
            else:
                results.append(FilterResult(True, f"{field_name} matches"))

        elif op_name in _OPS:
            threshold = _resolve_ref(filt["ref"], requirements)
            if not _OPS[op_name](prop_value, threshold):
                results.append(
                    FilterResult(
                        False, f"{field_name} {prop_value} fails {op_name} {threshold}"
                    )
                )
            else:
                results.append(FilterResult(True, f"{field_name} passes"))

        else:
            raise ValueError(f"Unknown filter op: {op_name!r}")

    return results


def must_have_score(
    prop: dict[str, Any],
    requirements: dict[str, Any],
) -> float:
    """
    Return the fraction of must-have features present in the property.
    1.0 = all must-haves satisfied; 0.0 = none.
    """
    must_haves: list[str] = requirements.get("must_haves", [])
    if not must_haves:
        return 1.0
    prop_features: list[str] = prop.get("features", [])
    hits = sum(1 for mh in must_haves if mh in prop_features)
    return hits / len(must_haves)


def is_eligible(
    prop: dict[str, Any],
    requirements: dict[str, Any],
    workflow_type: str,
    rules: dict[str, Any] | None = None,
) -> EligibilityResult:
    """
    Return an EligibilityResult for a single property.

    A property is eligible when:
    - All hard filters pass.
    - All must-haves are present (when must_have_match_required is True in rules).
    """
    if rules is None:
        rules = _load_rules(workflow_type)

    filter_results = check_hard_filters(prop, requirements, rules)
    failed = [r for r in filter_results if not r.passed]
    mh_score = must_have_score(prop, requirements)

    must_have_required: bool = rules.get("must_have_match_required", True)
    must_have_ok = (mh_score == 1.0) if must_have_required else True

    eligible = len(failed) == 0 and must_have_ok
    return EligibilityResult(
        eligible=eligible,
        failed_filters=failed,
        must_have_score=mh_score,
    )
