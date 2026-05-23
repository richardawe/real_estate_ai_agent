"""
Entry point for the advance (main agent tick) GitHub Actions workflow.

For each active workflow issue, examines state and runs the appropriate step.
Each invocation advances one step; it does not loop.
"""

from __future__ import annotations

import os

import requests

from engine.state_machine import State, current_state


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _list_active_issues(repo: str) -> list[dict]:
    active_states = ["flow:buy", "flow:rent"]
    issues = []
    for label in active_states:
        url = f"https://api.github.com/repos/{repo}/issues?labels={label}&state=open&per_page=100"
        resp = requests.get(url, headers=_gh_headers(), timeout=30)
        resp.raise_for_status()
        issues.extend(resp.json())
    seen = set()
    return [i for i in issues if not (i["number"] in seen or seen.add(i["number"]))]


def _get_issue(repo: str, number: int) -> dict:
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers=_gh_headers(), timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _post_comment(repo: str, number: int, body: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        headers=_gh_headers(), json={"body": body}, timeout=30,
    ).raise_for_status()


def _advance_issue(repo: str, issue: dict) -> None:
    labels = [l["name"] for l in issue.get("labels", [])]
    state = current_state(labels)
    number = issue["number"]

    # HITL-blocked states: do nothing, wait for /approve.
    blocked_states = {
        State.SHORTLIST_REVIEW, State.OFFER_DRAFT, State.LEASE_REVIEW,
        State.OFFER_SUBMITTED, State.CLOSING,
    }
    if state in blocked_states:
        return

    # Active states where the agent can make progress.
    if state == State.VIEWINGS:
        # Check for viewing confirmations (placeholder — IMAP not yet wired).
        pass
    elif state == State.DUE_DILIGENCE:
        # Check for inspector replies (placeholder — IMAP not yet wired).
        pass


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    issue_number = os.environ.get("ISSUE_NUMBER", "").strip()

    if issue_number:
        issues = [_get_issue(repo, int(issue_number))]
    else:
        issues = _list_active_issues(repo)

    for issue in issues:
        _advance_issue(repo, issue)
        print(f"Checked issue #{issue['number']}")


if __name__ == "__main__":
    main()
