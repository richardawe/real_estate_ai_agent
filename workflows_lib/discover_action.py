"""
Entry point for the discover GitHub Actions workflow.

Reads the target issue (or iterates over all discover/shortlist_review issues),
runs the discover step, and writes back via the GitHub API.
"""

from __future__ import annotations

import os
import sys

import requests

from workflows_lib.discover import run_discover
from workflows_lib.issue_io import parse_front_matter


def _gh_headers() -> dict[str, str]:
    token = os.environ["GITHUB_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_issue(repo: str, number: int) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    resp = requests.get(url, headers=_gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _list_issues_by_label(repo: str, labels: list[str]) -> list[dict]:
    label_str = ",".join(labels)
    url = f"https://api.github.com/repos/{repo}/issues?labels={label_str}&state=open&per_page=30"
    resp = requests.get(url, headers=_gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _update_issue(repo: str, number: int, body: str, labels: list[str]) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    requests.patch(url, headers=_gh_headers(), json={"body": body, "labels": labels}, timeout=30).raise_for_status()


def _post_comment(repo: str, number: int, body: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{number}/comments"
    requests.post(url, headers=_gh_headers(), json={"body": body}, timeout=30).raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    issue_number = os.environ.get("ISSUE_NUMBER", "")

    if issue_number:
        issues = [_get_issue(repo, int(issue_number))]
    else:
        discover_issues = _list_issues_by_label(repo, ["state:discover"])
        shortlist_issues = _list_issues_by_label(repo, ["state:shortlist_review"])
        issues = discover_issues + shortlist_issues

    for issue in issues:
        number = issue["number"]
        body = issue["body"] or ""
        labels = [l["name"] for l in issue.get("labels", [])]

        new_body, new_labels, comment = run_discover(body, labels)
        _update_issue(repo, number, new_body, new_labels)
        _post_comment(repo, number, comment)
        print(f"Processed issue #{number}")


if __name__ == "__main__":
    main()
