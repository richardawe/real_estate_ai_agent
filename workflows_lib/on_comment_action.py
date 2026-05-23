"""Entry point for the on_comment GitHub Actions workflow."""

from __future__ import annotations

import os

import requests

from workflows_lib.on_comment import UnknownCommandError, dispatch


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


def _update_issue(repo: str, number: int, body: str, labels: list[str], close: bool = False) -> None:
    payload: dict = {"body": body, "labels": labels}
    if close:
        payload["state"] = "closed"
    requests.patch(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers=_gh_headers(), json=payload, timeout=30,
    ).raise_for_status()


def _post_comment(repo: str, number: int, body: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        headers=_gh_headers(), json={"body": body}, timeout=30,
    ).raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    issue_number = int(os.environ["ISSUE_NUMBER"])
    comment_body = os.environ.get("COMMENT_BODY", "")

    issue = _get_issue(repo, issue_number)
    issue_body = issue.get("body", "")
    labels = [l["name"] for l in issue.get("labels", [])]

    try:
        result = dispatch(comment_body, issue_body, labels)
    except UnknownCommandError as exc:
        _post_comment(repo, issue_number, str(exc))
        return

    if result is None:
        return  # not a slash-command, ignore

    close = "state:completed" in result.new_labels and "state:completed" not in labels
    _update_issue(repo, issue_number, result.new_body, result.new_labels, close=close)
    _post_comment(repo, issue_number, result.reply)
    print(f"Dispatched command on issue #{issue_number}")


if __name__ == "__main__":
    main()
