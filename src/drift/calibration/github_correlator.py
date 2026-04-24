"""GitHub issue/PR → signal correlation for calibration evidence.

.. deprecated:: 2.9
    This module will be removed in v3.0. Use ``drift calibrate``
    with Bayesian Weight Calibration (ADR-035) instead.

Maps closed bug-issues to their fix-commits, then correlates affected
files with historical drift findings to produce TP/FN evidence.
"""

from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path
from typing import Any

from drift.calibration.feedback import FeedbackEvent
from drift.calibration.history import ScanSnapshot

warnings.warn(
    "drift.calibration.github_correlator is deprecated and will be removed "
    "in v3.0. Use 'drift calibrate' with Bayesian Weight Calibration instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)

# Match "Fixes #123", "Closes #456", "Resolves #789" in commit messages
_CLOSES_PATTERN = re.compile(
    r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)\b",
    re.IGNORECASE,
)


def _build_historical_findings_index(
    snapshots: list[ScanSnapshot],
) -> dict[str, set[str]]:
    """Build a {file_path → {signal_types}} index from historical snapshots."""
    index: dict[str, set[str]] = {}
    for snap in snapshots:
        for finding in snap.findings:
            fp = Path(finding.file_path).as_posix()
            index.setdefault(fp, set()).add(finding.signal_type)
    return index


def _extract_issue_labels(issue: dict[str, Any]) -> set[str] | None:
    """Return normalised label set for an issue, or None if issue is invalid."""
    if not isinstance(issue, dict):
        return None
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return None
    return {
        (lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)).lower()
        for lbl in labels
    }


def _correlate_bug_file(
    bug_file: str,
    issue_number: int,
    issue: dict[str, Any],
    historical_findings: dict[str, set[str]],
    seen: set[str],
    events: list[FeedbackEvent],
) -> None:
    """Append TP or FN FeedbackEvents for one bug file in-place."""
    signal_types = historical_findings.get(bug_file, set())
    if signal_types:
        for signal_type in signal_types:
            dedup_key = f"gh:{signal_type}:{bug_file}:{issue_number}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            events.append(
                FeedbackEvent(
                    signal_type=signal_type,
                    file_path=bug_file,
                    verdict="tp",
                    source="github_api",
                    evidence={
                        "issue_number": issue_number,
                        "issue_title": issue.get("title", ""),
                    },
                )
            )
    else:
        dedup_key = f"gh:_fn:{bug_file}:{issue_number}"
        if dedup_key in seen:
            return
        seen.add(dedup_key)
        events.append(
            FeedbackEvent(
                signal_type="_unattributed",
                file_path=bug_file,
                verdict="fn",
                source="github_api",
                evidence={
                    "issue_number": issue_number,
                    "issue_title": issue.get("title", ""),
                    "reason": "no_signal_flagged_buggy_file",
                },
            )
        )


def correlate_github_issues(
    snapshots: list[ScanSnapshot],
    issues: list[dict[str, Any]],
    pr_files_map: dict[int, list[str]],
    *,
    bug_labels: list[str] | None = None,
) -> list[FeedbackEvent]:
    """Correlate GitHub bug-issues with historical findings.

    For each closed bug-issue:
    1. Find PRs/commits that closed it (via pr_files_map keys).
    2. Get files changed in those PRs.
    3. Check if any historical finding existed for those files.
    4. Match → TP evidence (signal correctly warned about buggy file).
    5. No match → FN evidence (signal missed a buggy file).

    Args:
        snapshots: Historical scan snapshots.
        issues: GitHub issues (from GitHubClient.get_issues).
        pr_files_map: Mapping of PR number → list of changed files.
        bug_labels: Label names that identify bug-issues.

    Returns:
        List of FeedbackEvents with source ``"github_api"``.
    """
    if bug_labels is None:
        bug_labels = ["bug", "regression", "defect"]

    bug_label_set = {label.lower() for label in bug_labels}
    historical_findings = _build_historical_findings_index(snapshots)
    events: list[FeedbackEvent] = []
    seen: set[str] = set()

    for issue in issues:
        issue_labels = _extract_issue_labels(issue)
        if issue_labels is None:
            continue

        if not issue_labels & bug_label_set:
            continue

        issue_number = issue.get("number")
        if not isinstance(issue_number, int):
            continue

        bug_files: set[str] = set()
        for _pr_num, files in pr_files_map.items():
            bug_files.update(Path(f).as_posix() for f in files)

        if not bug_files:
            continue

        for bug_file in bug_files:
            _correlate_bug_file(bug_file, issue_number, issue, historical_findings, seen, events)

    return events
