"""Minimal GitHub REST API client for calibration evidence (stdlib-only).

Opt-in via ``calibration.github_token`` in drift.yaml or the
``DRIFT_GITHUB_TOKEN`` environment variable.  Uses only ``urllib.request``
to avoid adding a runtime dependency.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_ACCEPT = "application/vnd.github+json"
_API_VERSION = "2022-11-28"


class GitHubClient:
    """Minimal, rate-limit-aware GitHub REST v3 client.

    Designed for read-only calibration queries (issues, PRs, commits).
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        cache_dir: Path | None = None,
    ) -> None:
        self._token = token or os.environ.get("DRIFT_GITHUB_TOKEN", "")
        self._cache_dir = cache_dir
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._rate_remaining: int | None = None
        self._rate_reset: float | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    def _request(self, endpoint: str, *, params: dict[str, str] | None = None) -> Any:
        """Execute a GET request against the GitHub API."""
        # Rate-limit guard
        if (
            self._rate_remaining is not None
            and self._rate_remaining < 5
            and self._rate_reset
            and time.time() < self._rate_reset
        ):
            wait = self._rate_reset - time.time() + 1
            logger.warning("GitHub API rate limit near zero, waiting %.0fs", wait)
            time.sleep(min(wait, 60))  # cap at 60s

        url = f"{_API_BASE}{endpoint}"
        if params:
            query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url = f"{url}?{query}"

        headers: dict[str, str] = {
            "Accept": _ACCEPT,
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "drift-calibration/1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                # Update rate-limit tracking
                self._rate_remaining = _int_header(resp, "X-RateLimit-Remaining")
                self._rate_reset = _float_header(resp, "X-RateLimit-Reset")
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.warning("GitHub API error %d for %s", e.code, endpoint)
            raise
        except urllib.error.URLError as e:
            logger.warning("GitHub API connection error for %s: %s", endpoint, e.reason)
            raise

    def get_issues(
        self,
        owner: str,
        repo: str,
        *,
        labels: list[str] | None = None,
        state: str = "closed",
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch issues with optional label filter."""
        params: dict[str, str] = {
            "state": state,
            "per_page": str(per_page),
            "sort": "updated",
            "direction": "desc",
        }
        if labels:
            params["labels"] = ",".join(labels)

        endpoint = f"/repos/{owner}/{repo}/issues"
        return self._request(endpoint, params=params)  # type: ignore[no-any-return]

    def get_pull_requests_for_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> list[dict[str, Any]]:
        """Find PRs that reference an issue via timeline events."""
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/timeline"
        try:
            events = self._request(endpoint)
        except urllib.error.HTTPError:
            return []

        prs: list[dict[str, Any]] = []
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict) and event.get("event") == "cross-referenced":
                    source = event.get("source", {})
                    issue = source.get("issue", {})
                    if issue.get("pull_request"):
                        prs.append(issue)
        return prs

    def get_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[str]:
        """Get list of files changed in a pull request."""
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
        try:
            files = self._request(endpoint, params={"per_page": "100"})
        except urllib.error.HTTPError:
            return []

        if isinstance(files, list):
            return [f.get("filename", "") for f in files if isinstance(f, dict)]
        return []


def _int_header(resp: Any, name: str) -> int | None:
    val = resp.headers.get(name)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return None


def _float_header(resp: Any, name: str) -> float | None:
    val = resp.headers.get(name)
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    return None
