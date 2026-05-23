"""
Entry point for the nightly GitHub Actions workflow.

Tasks:
- Re-run discover on stale shortlists (no activity in 48h).
- Send digest comment to any workflow without activity in 48h.
- Archive completed workflows older than 90 days.
- Alert when a workflow exceeds the token budget cap.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

_TOKEN_BUDGET_CAP = 500_000


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _list_issues(repo: str, labels: str, state: str = "open") -> list[dict]:
    url = f"https://api.github.com/repos/{repo}/issues?labels={labels}&state={state}&per_page=100"
    resp = requests.get(url, headers=_gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post_comment(repo: str, number: int, body: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        headers=_gh_headers(), json={"body": body}, timeout=30,
    ).raise_for_status()


def _close_issue(repo: str, number: int) -> None:
    requests.patch(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers=_gh_headers(), json={"state": "closed"}, timeout=30,
    ).raise_for_status()


def _last_activity(issue: dict) -> datetime:
    ts = issue.get("updated_at") or issue.get("created_at")
    return datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=timezone.utc)


def main() -> None:
    from workflows_lib.issue_io import get_field

    repo = os.environ["GITHUB_REPOSITORY"]
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=48)
    archive_threshold = now - timedelta(days=90)

    # Digest for stale active workflows.
    for label in ["flow:buy", "flow:rent"]:
        for issue in _list_issues(repo, label):
            if _last_activity(issue) < stale_threshold:
                _post_comment(
                    repo, issue["number"],
                    "This workflow has had no activity in 48 hours. "
                    "Reply with a slash-command to continue, or `/abort` to cancel.",
                )

    # Token budget alerts.
    for label in ["flow:buy", "flow:rent"]:
        for issue in _list_issues(repo, label):
            usage = get_field(issue.get("body", ""), "token_usage", 0) or 0
            if usage > _TOKEN_BUDGET_CAP:
                _post_comment(
                    repo, issue["number"],
                    f"Warning: this workflow has used {usage:,} tokens "
                    f"(cap: {_TOKEN_BUDGET_CAP:,}). Further LLM calls are paused.",
                )

    # Archive completed issues older than 90 days.
    for label in ["flow:buy", "flow:rent"]:
        for issue in _list_issues(repo, f"{label},state:completed", state="open"):
            if _last_activity(issue) < archive_threshold:
                _close_issue(repo, issue["number"])
                print(f"Archived issue #{issue['number']}")


if __name__ == "__main__":
    main()
