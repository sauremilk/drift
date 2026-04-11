"""CI environment detection for ``drift ci``."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CIContext:
    """Detected CI environment metadata."""

    provider: str
    base_ref: str | None = None
    is_pr: bool = False
    pr_number: int | None = None


def detect_ci_environment() -> CIContext | None:
    """Auto-detect CI provider and extract PR context from env vars.

    Returns *None* when no CI environment is detected.
    """
    if os.getenv("GITHUB_ACTIONS") == "true":
        base_ref = os.getenv("GITHUB_BASE_REF") or None
        pr_number_str = os.getenv("GITHUB_PR_NUMBER", "")
        # GITHUB_REF_TYPE and GITHUB_EVENT_NAME help detect PRs
        is_pr = bool(base_ref) or os.getenv("GITHUB_EVENT_NAME") in (
            "pull_request",
            "pull_request_target",
        )
        pr_number: int | None = None
        if pr_number_str.isdigit():
            pr_number = int(pr_number_str)
        return CIContext(
            provider="github-actions",
            base_ref=base_ref or "origin/main",
            is_pr=is_pr,
            pr_number=pr_number,
        )

    if os.getenv("GITLAB_CI"):
        base_ref = os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME")
        is_pr = bool(base_ref)
        mr_iid = os.getenv("CI_MERGE_REQUEST_IID", "")
        return CIContext(
            provider="gitlab-ci",
            base_ref=f"origin/{base_ref}" if base_ref else "origin/main",
            is_pr=is_pr,
            pr_number=int(mr_iid) if mr_iid.isdigit() else None,
        )

    if os.getenv("CIRCLECI"):
        branch = os.getenv("CIRCLE_BRANCH", "main")
        pr_url = os.getenv("CIRCLE_PULL_REQUEST", "")
        return CIContext(
            provider="circleci",
            base_ref=f"origin/{branch}",
            is_pr=bool(pr_url),
        )

    if os.getenv("AZURE_PIPELINES") or os.getenv("BUILD_BUILDID"):
        base_ref = os.getenv("SYSTEM_PULLREQUEST_TARGETBRANCH")
        is_pr = bool(base_ref)
        return CIContext(
            provider="azure-pipelines",
            base_ref=f"origin/{base_ref}" if base_ref else "origin/main",
            is_pr=is_pr,
        )

    if os.getenv("CI", "").lower() == "true":
        return CIContext(provider="generic-ci", base_ref="origin/main", is_pr=False)

    return None
