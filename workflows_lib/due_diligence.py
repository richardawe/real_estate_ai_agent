"""
Due diligence coordination (buy path).

After offer acceptance (state:due_diligence), the agent:
1. Posts a checklist comment listing what the user needs to arrange.
2. Monitors for user uploads (inspector/appraiser replies) via issue comments.
3. When the user posts /approve after uploading all documents, advances to closing.

The agent never contacts inspectors or appraisers directly — that stays HITL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.state_machine import State, add_hitl
from workflows_lib.issue_io import get_field, parse_front_matter

_RULES_DIR = Path(__file__).parent.parent / "rules"


def due_diligence_checklist_comment(
    issue_body: str,
    workflow_type: str = "buy",
) -> str:
    """
    Generate a due-diligence checklist comment for the user.
    Items come from the rules YAML — not hardcoded here.
    """
    import yaml

    rules_file = "buying_v1.yaml" if workflow_type == "buy" else "renting_v1.yaml"
    with (_RULES_DIR / rules_file).open() as f:
        rules = yaml.safe_load(f)

    items = rules.get("due_diligence_checklist", [])
    checklist = "\n".join(f"- [ ] {item.replace('_', ' ').title()}" for item in items)

    return (
        "## Due diligence checklist\n\n"
        "Please arrange the following and upload the results as issue attachments "
        "or link them in a comment. Reply `/approve` when all items are complete.\n\n"
        + checklist
        + "\n\n"
        "**Note:** The agent will summarise any inspection report you upload. "
        "A solicitor should review all legal documents before you proceed to exchange."
    )


def check_documents_complete(issue_body: str, workflow_type: str = "buy") -> bool:
    """
    Placeholder check: returns True when the user has indicated completion.
    In production this parses uploaded document references from comments.
    Currently always returns False to keep the workflow paused until /approve.
    """
    return False
