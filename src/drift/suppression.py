"""Inline suppression support — ``# drift:ignore`` comments."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from drift.models import FileInfo, Finding, FindingStatus

# Matches Python-style comments:  # drift:ignore  or  # drift:ignore[AVS,PFS]
_PY_PATTERN = re.compile(r"#\s*drift:ignore(?:\[([A-Z_,]+)\])?")
# Matches JS/TS-style comments:  // drift:ignore  or  // drift:ignore[AVS,PFS]
_JS_PATTERN = re.compile(r"//\s*drift:ignore(?:\[([A-Z_,]+)\])?")

_PATTERN_BY_LANG = {
    "python": _PY_PATTERN,
    "typescript": _JS_PATTERN,
    "tsx": _JS_PATTERN,
    "javascript": _JS_PATTERN,
    "jsx": _JS_PATTERN,
}


@dataclass(frozen=True)
class InlineSuppression:
    """Structured representation of a single inline ``drift:ignore`` directive."""

    file_path: str
    line_number: int
    signals: set[str] | None
    until: date | None = None
    reason: str | None = None


_UNTIL_PATTERN = re.compile(r"\buntil:(\d{4}-\d{2}-\d{2})\b")
_REASON_PATTERN = re.compile(r"\breason:(.+)$")


def _parse_until(text: str) -> date | None:
    """Parse optional ``until:YYYY-MM-DD`` metadata from comment tail."""
    match = _UNTIL_PATTERN.search(text)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _parse_reason(text: str) -> str | None:
    """Parse optional ``reason:...`` metadata from comment tail."""
    match = _REASON_PATTERN.search(text)
    if match is None:
        return None
    reason = match.group(1).strip()
    return reason or None


def collect_inline_suppressions(
    files: list[FileInfo],
    repo_path: Path,
) -> list[InlineSuppression]:
    """Collect inline suppression directives including optional metadata."""
    from drift.config import SIGNAL_ABBREV

    entries: list[InlineSuppression] = []

    for finfo in files:
        pattern = _PATTERN_BY_LANG.get(finfo.language)
        if pattern is None:
            continue
        full_path = repo_path / finfo.path
        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            match = pattern.search(line)
            if match is None:
                continue

            raw = match.group(1)
            signals: set[str] | None = None
            if raw:
                resolved: set[str] = set()
                for token in raw.split(","):
                    signal = token.strip()
                    if not signal:
                        continue
                    abbrev = signal.upper()
                    if abbrev in SIGNAL_ABBREV:
                        resolved.add(SIGNAL_ABBREV[abbrev])
                    else:
                        resolved.add(signal.lower())
                signals = resolved

            tail = line[match.end() :]
            entries.append(
                InlineSuppression(
                    file_path=finfo.path.as_posix(),
                    line_number=line_no,
                    signals=signals,
                    until=_parse_until(tail),
                    reason=_parse_reason(tail),
                )
            )

    return entries


def scan_suppressions(
    files: list[FileInfo],
    repo_path: Path,
) -> dict[tuple[str, int], set[str] | None]:
    """Scan source files for ``drift:ignore`` comments.

    Returns a mapping of ``(posix_path, line_number)`` to the set of signal
    type *values* that should be suppressed.  ``None`` means *all* signals.
    """
    suppressions: dict[tuple[str, int], set[str] | None] = {}

    for entry in collect_inline_suppressions(files, repo_path):
        suppressions[(entry.file_path, entry.line_number)] = entry.signals

    return suppressions


def filter_findings(
    findings: list[Finding],
    suppressions: Mapping[tuple[str, int], set[str] | None],
) -> tuple[list[Finding], list[Finding]]:
    """Partition findings into *active* and *suppressed*.

    A finding is suppressed when any line in its ``[start_line, end_line]``
    range has a matching entry in *suppressions* that either covers all
    signals (``None``) or includes the finding's signal type.
    """
    if not suppressions:
        return findings, []

    active: list[Finding] = []
    suppressed: list[Finding] = []

    for f in findings:
        if f.file_path is None or f.start_line is None:
            active.append(f)
            continue

        end_line = f.end_line if f.end_line is not None else f.start_line
        start_line = min(f.start_line, end_line)
        end_line = max(f.start_line, end_line)

        is_suppressed = False
        for line_no in range(start_line, end_line + 1):
            key = (f.file_path.as_posix(), line_no)
            entry = suppressions.get(key)
            if entry is None and key not in suppressions:
                continue
            if entry is None or f.signal_type in entry:
                is_suppressed = True
                break

        if is_suppressed:
            f.status = FindingStatus.SUPPRESSED
            f.status_set_by = "inline_comment"
            f.status_reason = "Suppressed by drift:ignore comment"
            suppressed.append(f)
        else:
            f.status = FindingStatus.ACTIVE
            active.append(f)

    return active, suppressed
