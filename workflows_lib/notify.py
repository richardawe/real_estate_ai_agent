"""
Post structured comments to GitHub Issues.

All comments go through this module so formatting is consistent and every
outbound message is logged. The LLM drafts the text but this module sends it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

_PROMPTS_DIR = Path(__file__).parent.parent / "engine" / "prompts"


def _gh_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def post_comment(repo: str, issue_number: int, body: str) -> dict[str, Any]:
    """Post a comment to a GitHub Issue. Returns the API response dict."""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    resp = requests.post(url, headers=_gh_headers(), json={"body": body}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_hitl_template(kind: str) -> str:
    """Load a HITL comment template by kind name."""
    path = _PROMPTS_DIR / "hitl" / f"{kind}.md"
    return path.read_text()


def render_hitl_comment(kind: str, **kwargs: Any) -> str:
    """Render a HITL comment template with the supplied keyword arguments."""
    template = load_hitl_template(kind)
    return template.format(**kwargs)
