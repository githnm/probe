"""GitHub PR comment poster."""

from __future__ import annotations

import json
import urllib.request

from probe import Report
from probe.report import render_markdown

COMMENT_MARKER = "<!-- probe-report -->"
SEVERITY_ICON = {"info": "ℹ️", "warn": "⚠️", "block": "❌"}


def format_comment(report: Report) -> str:
    icon = SEVERITY_ICON.get(report.severity, "")
    lines = [
        COMMENT_MARKER,
        f"# {icon} Probe: {report.severity.upper()}",
        "",
        render_markdown(report),
        "",
        "---",
        "*Posted by [Probe](https://github.com/probe-sql/probe) — "
        "a SQL reviewer that reports what changed, with proof.*",
    ]
    return "\n".join(lines)


def post_comment(
    body: str,
    repo: str,
    pr_number: int,
    token: str,
) -> dict:
    existing_id = _find_existing_comment(repo, pr_number, token)
    if existing_id:
        return _update_comment(body, repo, existing_id, token)
    return _create_comment(body, repo, pr_number, token)


def _find_existing_comment(
    repo: str, pr_number: int, token: str
) -> int | None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    data = _gh_request("GET", url, token)
    for c in data:
        if COMMENT_MARKER in c.get("body", ""):
            return c["id"]
    return None


def _create_comment(
    body: str, repo: str, pr_number: int, token: str
) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    return _gh_request("POST", url, token, {"body": body})


def _update_comment(
    body: str, repo: str, comment_id: int, token: str
) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}"
    return _gh_request("PATCH", url, token, {"body": body})


def _gh_request(
    method: str, url: str, token: str, payload: dict | None = None
) -> dict | list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())
