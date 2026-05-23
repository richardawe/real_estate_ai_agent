"""
Read and write YAML front-matter on GitHub Issue bodies.

Convention: the issue body begins with a YAML block delimited by --- markers.
Everything after the closing --- is free-text (agent comments, markdown prose).
All helpers are pure functions; they take a body string and return a new one.
The caller is responsible for writing back to the GitHub API.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import yaml


_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_front_matter(body: str) -> tuple[dict[str, Any], str]:
    """
    Split an issue body into (front_matter_dict, rest_of_body).
    Returns ({}, body) when no front-matter block is present.
    """
    match = _FRONT_MATTER_RE.match(body)
    if not match:
        return {}, body
    fm: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
    rest = body[match.end():].lstrip("\n")
    return fm, rest


def render_front_matter(fm: dict[str, Any], body: str) -> str:
    """Serialise front-matter dict + body back to a full issue body string."""
    fm_yaml = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    return f"---\n{fm_yaml}\n---\n\n{body}"


def update_field(body: str, field: str, value: Any) -> str:
    """Set a single front-matter field, preserving everything else."""
    fm, rest = parse_front_matter(body)
    fm[field] = value
    return render_front_matter(fm, rest)


def get_field(body: str, field: str, default: Any = None) -> Any:
    """Read a single front-matter field."""
    fm, _ = parse_front_matter(body)
    return fm.get(field, default)


def append_to_list(body: str, field: str, value: Any) -> str:
    """Append value to a list field in front-matter; idempotent."""
    fm, rest = parse_front_matter(body)
    current: list[Any] = fm.get(field) or []
    if value not in current:
        current = current + [value]
    fm[field] = current
    return render_front_matter(fm, rest)


def remove_from_list(body: str, field: str, value: Any) -> str:
    """Remove value from a list field in front-matter."""
    fm, rest = parse_front_matter(body)
    current: list[Any] = fm.get(field) or []
    fm[field] = [v for v in current if v != value]
    return render_front_matter(fm, rest)


def build_initial_body(fm: dict[str, Any], prose: str = "") -> str:
    """Create a fresh issue body from a front-matter dict and optional prose."""
    return render_front_matter(fm, prose)


def new_workflow_front_matter(
    workflow_id: str,
    workflow_type: str,
    jurisdiction: str,
    requirements: dict[str, Any],
    encrypted_pii: str,
    schema_version: int = 1,
) -> dict[str, Any]:
    """
    Build the canonical front-matter dict for a new workflow issue.
    The caller supplies pre-encrypted PII.
    """
    from datetime import datetime, timezone

    return {
        "workflow_id": workflow_id,
        "type": workflow_type,
        "schema_version": schema_version,
        "jurisdiction": jurisdiction,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "encrypted_pii": encrypted_pii,
        "requirements": requirements,
        "shortlist": [],
        "selected_property_id": None,
        "current_transaction": None,
        "documents": [],
        "token_usage": 0,
    }
