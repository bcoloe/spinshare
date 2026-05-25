"""Thin HTTP adapter for the GitHub Issues API."""

import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

log = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_API_VERSION = "2022-11-28"


@dataclass
class GitHubIssueResult:
    number: int
    html_url: str


def create_issue(*, title: str, body: str, label: str) -> GitHubIssueResult:
    """Create a GitHub issue in the configured repository.

    Args:
        title: The issue title.
        body: Markdown-formatted body of the issue.
        label: GitHub label to apply (e.g. "bug" or "enhancement").

    Returns:
        GitHubIssueResult with the created issue number and HTML URL.

    Raises:
        HTTPException 503: If GITHUB_TOKEN or GITHUB_REPO is not configured.
        HTTPException 502: If the GitHub API returns a non-success response.
    """
    settings = get_settings()

    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration not configured",
        )

    resp = httpx.post(
        f"{_GITHUB_API_BASE}/repos/{settings.GITHUB_REPO}/issues",
        json={"title": title, "body": body, "labels": [label]},
        headers={
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        },
        timeout=10,
    )

    if not resp.is_success:
        log.error(
            "GitHub issue creation failed: status=%d body=%r",
            resp.status_code,
            resp.text[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create GitHub issue",
        )

    data = resp.json()
    return GitHubIssueResult(number=data["number"], html_url=data["html_url"])
