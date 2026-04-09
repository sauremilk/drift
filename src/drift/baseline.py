"""Baseline management — save, load, and compare finding snapshots.

A baseline captures a fingerprint of every current finding so that subsequent
runs can distinguish *new* findings from *known* ones.  This lets teams adopt
drift on existing codebases without being overwhelmed by pre-existing issues.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from drift import __version__
from drift.api_helpers import build_drift_score_scope
from drift.models import Finding, RepoAnalysis

# ---------------------------------------------------------------------------
# Finding fingerprint
# ---------------------------------------------------------------------------


def finding_fingerprint(f: Finding) -> str:
    """Return a deterministic, content-based fingerprint for a finding.

    The fingerprint is stable across runs as long as the finding's core
    identity (signal, file, line range, title) has not changed.
    """
    parts = [
        f.signal_type,
        f.file_path.as_posix() if f.file_path else "",
        str(f.start_line or 0),
        str(f.end_line or 0),
        f.title,
    ]
    raw = "\0".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Baseline file I/O
# ---------------------------------------------------------------------------

_BASELINE_VERSION = 1


def save_baseline(analysis: RepoAnalysis, path: Path) -> None:
    """Write a baseline file from an analysis result."""
    entries: list[dict[str, Any]] = []
    for f in analysis.findings:
        entries.append({
            "fingerprint": finding_fingerprint(f),
            "signal": f.signal_type,
            "severity": f.severity.value,
            "file": f.file_path.as_posix() if f.file_path else None,
            "start_line": f.start_line,
            "title": f.title,
        })

    data: dict[str, Any] = {
        "baseline_version": _BASELINE_VERSION,
        "drift_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "drift_score": analysis.drift_score,
        "drift_score_scope": build_drift_score_scope(context="repo"),
        "finding_count": len(entries),
        "findings": entries,
    }

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> set[str]:
    """Load a baseline file and return the set of finding fingerprints."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict) or "findings" not in data:
        msg = f"Invalid baseline file: {path}"
        raise ValueError(msg)
    return {entry["fingerprint"] for entry in data["findings"]}


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def baseline_diff(
    findings: list[Finding],
    baseline_fingerprints: set[str],
) -> tuple[list[Finding], list[Finding]]:
    """Split findings into (new, known) relative to a baseline.

    Returns:
        A tuple of ``(new_findings, known_findings)`` where *new* means
        the finding's fingerprint does not appear in the baseline.
    """
    new: list[Finding] = []
    known: list[Finding] = []
    for f in findings:
        fp = finding_fingerprint(f)
        if fp in baseline_fingerprints:
            known.append(f)
        else:
            new.append(f)
    return new, known
