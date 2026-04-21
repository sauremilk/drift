"""Baseline management — save, load, and compare finding snapshots.

A baseline captures a fingerprint of every current finding so that subsequent
runs can distinguish *new* findings from *known* ones.  This lets teams adopt
drift on existing codebases without being overwhelmed by pre-existing issues.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from drift import __version__
from drift.models import Finding, RepoAnalysis
from drift.response_shaping import build_drift_score_scope

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Finding fingerprint — v2 schema (ADR-082)
# ---------------------------------------------------------------------------
#
# v1 used (signal, file, start_line, end_line, title) which shifted after any
# line change or metric-title change. v2 uses (signal, file, symbol_identity,
# stable_title) and is therefore line-independent.


# Matches integer runs that represent metrics embedded in titles. Keeps the
# structural text around them (e.g. "complexity 19" → "complexity <N>").
_METRIC_INT_RE = re.compile(r"\d+")

# Matches a trailing parenthesised list of file:line references which some
# signal titles append (e.g. " (scripts/foo.py:87)").
_TRAILING_REFS_RE = re.compile(r"\s*\([^()]*:\d+[^()]*\)\s*$")


def _symbol_identity(f: Finding) -> str:
    """Return the most stable symbol identity available for a finding.

    Preference order:
        1. ``logical_location.fully_qualified_name``
        2. ``logical_location.name``
        3. ``symbol``
        4. empty string (file-scope only)

    Accepts finding-like objects that may lack either attribute
    (e.g. ``SimpleNamespace`` test doubles) and falls back gracefully.
    """
    loc = getattr(f, "logical_location", None)
    if loc is not None:
        fqn = getattr(loc, "fully_qualified_name", None)
        if fqn:
            return str(fqn)
        name = getattr(loc, "name", None)
        if name:
            return str(name)
    sym = getattr(f, "symbol", None)
    if sym:
        return str(sym)
    return ""


def _stable_title(title: str) -> str:
    """Return a title with volatile metrics and trailing refs stripped.

    This is used by the v2 fingerprint so that unrelated edits to a metric
    count in the title (e.g. "2 variants" → "3 variants") do not shift the
    fingerprint.
    """
    if not title:
        return ""
    stripped = _TRAILING_REFS_RE.sub("", title)
    return _METRIC_INT_RE.sub("<N>", stripped)


def finding_fingerprint_v1(f: Finding) -> str:
    """Return the v1 (legacy, line-based) fingerprint for a finding.

    Kept for baseline migration and regression testing. Do not use in new
    code paths — v1 is line-shift-sensitive (see ADR-082).
    """
    file_path = getattr(f, "file_path", None)
    parts = [
        f.signal_type,
        file_path.as_posix() if file_path else "",
        str(getattr(f, "start_line", None) or 0),
        str(getattr(f, "end_line", None) or 0),
        getattr(f, "title", "") or "",
    ]
    raw = "\0".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def finding_fingerprint_v2(f: Finding) -> str:
    """Return the v2 (symbol-based, line-independent) fingerprint."""
    file_path = getattr(f, "file_path", None)
    parts = [
        f.signal_type,
        file_path.as_posix() if file_path else "",
        _symbol_identity(f),
        _stable_title(getattr(f, "title", "") or ""),
    ]
    raw = "\0".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def finding_fingerprint(f: Finding) -> str:
    """Return the canonical (v2) fingerprint for a finding.

    This is the public API used by baseline, diff-HEAD subtraction, and
    finding-id exposure. See ADR-082 for the stability contract.
    """
    return finding_fingerprint_v2(f)


def stable_title(title: str) -> str:
    """Public helper: return a title stripped of volatile metrics.

    Exposed for the fuzzy HEAD-subtraction pass in ``drift.api.diff``.
    """
    return _stable_title(title)


# ---------------------------------------------------------------------------
# Baseline file I/O
# ---------------------------------------------------------------------------

_BASELINE_VERSION = 2


def save_baseline(analysis: RepoAnalysis, path: Path) -> None:
    """Write a baseline file from an analysis result.

    Writes baseline schema v2. Each entry contains both the canonical
    v2 ``fingerprint`` and a legacy ``fingerprint_v1`` for backwards
    compatibility with older drift versions during the migration window
    (see ADR-082).
    """
    entries: list[dict[str, Any]] = []
    for f in analysis.findings:
        entries.append({
            "fingerprint": finding_fingerprint_v2(f),
            "fingerprint_v1": finding_fingerprint_v1(f),
            "signal": f.signal_type,
            "severity": f.severity.value,
            "file": f.file_path.as_posix() if f.file_path else None,
            "symbol": _symbol_identity(f) or None,
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

    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        Path(tmp).replace(path)
    except OSError:
        with suppress(OSError):
            Path(tmp).unlink(missing_ok=True)
        raise


def load_baseline(path: Path) -> set[str]:
    """Load a baseline file and return the set of finding fingerprints.

    The returned set always contains v2 fingerprints (the canonical schema).
    For baseline files written by older drift versions (schema v1 without
    ``fingerprint_v1`` field), the stored ``fingerprint`` entries are v1 and
    included as-is so that diff comparisons still match legacy analyses.
    A warning is emitted in that case; consumers should regenerate with
    ``drift baseline save`` to get the stable v2 schema.
    """
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict) or "findings" not in data:
        msg = f"Invalid baseline file: {path}"
        raise ValueError(msg)
    stored_version = data.get("drift_version")
    if stored_version and stored_version != __version__:
        logger.warning(
            "Baseline was created with drift %s but running drift %s. "
            "Fingerprints may not match — consider regenerating the baseline "
            "with 'drift baseline save'.",
            stored_version,
            __version__,
        )

    schema_version = data.get("baseline_version", 1)
    fingerprints: set[str] = set()
    for entry in data["findings"]:
        # Always include the canonical 'fingerprint' field, whatever schema
        # version wrote it. ``baseline_diff`` performs the v1/v2 compatibility
        # lookup on the finding side (checks both v1 and v2 against this set),
        # so returning only the stored canonical fingerprint is sufficient.
        fingerprints.add(entry["fingerprint"])

    if schema_version < _BASELINE_VERSION:
        logger.warning(
            "Baseline schema v%s is older than current v%s. Line-shifts "
            "and metric-title changes may appear as new findings. Run "
            "'drift baseline save' to upgrade.",
            schema_version,
            _BASELINE_VERSION,
        )

    return fingerprints


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def baseline_diff(
    findings: list[Finding],
    baseline_fingerprints: set[str],
) -> tuple[list[Finding], list[Finding]]:
    """Split findings into (new, known) relative to a baseline.

    A finding is considered *known* if **either** its canonical (v2) or
    legacy (v1) fingerprint appears in ``baseline_fingerprints``. This dual
    lookup keeps new drift runtimes compatible with v1 baselines produced
    by older versions during the migration window (see ADR-082).

    Returns:
        A tuple of ``(new_findings, known_findings)``.
    """
    new: list[Finding] = []
    known: list[Finding] = []
    for f in findings:
        fp_v2 = finding_fingerprint_v2(f)
        fp_v1 = finding_fingerprint_v1(f)
        if fp_v2 in baseline_fingerprints or fp_v1 in baseline_fingerprints:
            known.append(f)
        else:
            new.append(f)
    return new, known
