"""GitHub issue/PR → signal correlation for calibration evidence.

Maps closed bug-issues to their fix-commits, then correlates affected
files with historical drift findings to produce TP/FN evidence.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from drift.calibration.feedback import FeedbackEvent
from drift.calibration.history import ScanSnapshot

logger = logging.getLogger(__name__)

# Match "Fixes #123", "Closes #456", "Resolves #789" in commit messages
_CLOSES_PATTERN = re.compile(
    r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)\b",
    re.IGNORECASE,
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

    # Build a set of all historically flagged (signal_type, file_path) pairs
    historical_findings: dict[str, set[str]] = {}  # file_path → {signal_types}
    for snap in snapshots:
        for finding in snap.findings:
            fp = Path(finding.file_path).as_posix()
            if fp not in historical_findings:
                historical_findings[fp] = set()
            historical_findings[fp].add(finding.signal_type)

    events: list[FeedbackEvent] = []
    seen: set[str] = set()

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        # Filter to bug-labeled issues only
        labels = issue.get("labels", [])
        if isinstance(labels, list):
            issue_labels = {
                (lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)).lower()
                for lbl in labels
            }
        else:
            continue

        if not issue_labels & bug_label_set:
            continue

        issue_number = issue.get("number")
        if not isinstance(issue_number, int):
            continue

        # Collect all files from PRs that closed this issue
        bug_files: set[str] = set()
        for _pr_num, files in pr_files_map.items():
            bug_files.update(Path(f).as_posix() for f in files)

        if not bug_files:
            continue

        # Correlate bug files with historical findings
        for bug_file in bug_files:
            signal_types = historical_findings.get(bug_file, set())

            if signal_types:
                # TP: drift had flagged this file, and it turned out buggy
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
                # FN: bug in file, but no drift signal had warned about it
                # We attribute FN to all active signals as weak evidence
                dedup_key = f"gh:_fn:{bug_file}:{issue_number}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                # Record FN without attributing to a specific signal
                # (the profile builder will distribute FN across all signals)
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

    return events
