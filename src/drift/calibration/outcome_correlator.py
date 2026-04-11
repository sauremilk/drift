"""Git-outcome correlation engine for calibration evidence.

Correlates historical drift findings with subsequent defect-fix commits
to generate TP/FP evidence for signal weight calibration.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from drift.calibration.feedback import FeedbackEvent
from drift.calibration.history import ScanSnapshot

# Matches commit messages indicating a bug fix (same as git_history.py)
_DEFECT_PATTERN = re.compile(
    r"\b(fix|bug|hotfix|revert|patch|regression|broken|crash|error)\b",
    re.IGNORECASE,
)


def correlate_outcomes(
    snapshots: list[ScanSnapshot],
    commits: list[dict[str, object]],
    *,
    correlation_window_days: int = 30,
    weak_fp_window_days: int = 60,
) -> list[FeedbackEvent]:
    """Correlate scan findings with defect-fix commits.

    For each finding in historical snapshots, check whether a defect-fix
    commit touched the same file within *correlation_window_days* after
    the scan.  Matches produce TP evidence; findings without any
    defect-fix after *weak_fp_window_days* produce weak FP evidence.

    Args:
        snapshots: Historical scan snapshots (oldest first).
        commits: List of commit dicts with keys ``timestamp`` (ISO str),
            ``message`` (str), ``files_changed`` (list[str]).
        correlation_window_days: Window for TP correlation.
        weak_fp_window_days: Window after which no fix → weak FP.

    Returns:
        List of FeedbackEvents with source ``"git_correlation"``.
    """
    if not snapshots:
        return []

    # Pre-process commits: only defect-fix commits, sorted by time
    defect_commits = []
    for c in commits:
        msg = str(c.get("message", ""))
        if _DEFECT_PATTERN.search(msg):
            ts_raw = c.get("timestamp")
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw)
                except ValueError:
                    continue
            elif isinstance(ts_raw, datetime):
                ts = ts_raw
            else:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            files = c.get("files_changed", [])
            if isinstance(files, list):
                defect_commits.append((ts, set(str(f) for f in files)))
    defect_commits.sort(key=lambda x: x[0])

    now = datetime.now(UTC)
    events: list[FeedbackEvent] = []
    seen: set[str] = set()  # dedup key: signal_type:file_path

    for snap in snapshots:
        scan_ts = _parse_ts(snap.timestamp)
        if scan_ts is None:
            continue

        tp_deadline = scan_ts + timedelta(days=correlation_window_days)
        fp_deadline = scan_ts + timedelta(days=weak_fp_window_days)

        for finding in snap.findings:
            dedup_key = f"{finding.signal_type}:{finding.file_path}"
            if dedup_key in seen:
                continue

            matched = False
            for commit_ts, commit_files in defect_commits:
                if commit_ts < scan_ts:
                    continue
                if commit_ts > tp_deadline:
                    break
                # Normalize paths for comparison
                finding_path = Path(finding.file_path).as_posix()
                if any(Path(f).as_posix() == finding_path for f in commit_files):
                    events.append(
                        FeedbackEvent(
                            signal_type=finding.signal_type,
                            file_path=finding.file_path,
                            verdict="tp",
                            source="git_correlation",
                            evidence={
                                "commit_ts": commit_ts.isoformat(),
                                "days_after_scan": (commit_ts - scan_ts).days,
                            },
                        )
                    )
                    seen.add(dedup_key)
                    matched = True
                    break

            if not matched and now > fp_deadline:
                events.append(
                    FeedbackEvent(
                        signal_type=finding.signal_type,
                        file_path=finding.file_path,
                        verdict="fp",
                        source="git_correlation",
                        evidence={
                            "reason": "no_defect_fix_within_window",
                            "window_days": weak_fp_window_days,
                        },
                    )
                )
                seen.add(dedup_key)

    return events


def _parse_ts(raw: str) -> datetime | None:
    """Parse an ISO timestamp, returning None on failure."""
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts
    except ValueError:
        return None
