"""Entry point for the intake GitHub Actions workflow."""

from __future__ import annotations

import json
import os

import requests

from workflows_lib.intake import process_intake


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_issue(repo: str, number: int) -> dict:
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers=_gh_headers(), timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _update_issue(repo: str, number: int, body: str, labels: list[str]) -> None:
    requests.patch(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers=_gh_headers(),
        json={"body": body, "labels": labels},
        timeout=30,
    ).raise_for_status()


def _post_comment(repo: str, number: int, body: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        headers=_gh_headers(),
        json={"body": body},
        timeout=30,
    ).raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    issue_number = int(os.environ["ISSUE_NUMBER"])
    raw_intake = json.loads(os.environ.get("INTAKE_TEXT", '""'))
    workflow_type = os.environ.get("WORKFLOW_TYPE", "buy")

    issue = _get_issue(repo, issue_number)

    # When triggered from an issue.opened event, use the issue body as intake text.
    if not raw_intake:
        raw_intake = issue.get("body", "")

    try:
        new_body, new_labels, tokens = process_intake(raw_intake, workflow_type)
    except Exception as exc:
        _post_comment(repo, issue_number, f"Intake failed: {exc}\nPlease clarify your requirements.")
        raise

    _update_issue(repo, issue_number, new_body, new_labels)
    _post_comment(
        repo, issue_number,
        f"Requirements extracted ({tokens} tokens). Starting property search now.",
    )
    print(f"Intake complete for issue #{issue_number}")


if __name__ == "__main__":
    main()
