"""Inline suppression support — ``# drift:ignore`` comments."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from drift.models import FileInfo, Finding

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


def scan_suppressions(
    files: list[FileInfo],
    repo_path: Path,
) -> dict[tuple[str, int], set[str] | None]:
    """Scan source files for ``drift:ignore`` comments.

    Returns a mapping of ``(posix_path, line_number)`` to the set of signal
    type *values* that should be suppressed.  ``None`` means *all* signals.
    """
    suppressions: dict[tuple[str, int], set[str] | None] = {}

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
            m = pattern.search(line)
            if m is None:
                continue
            raw = m.group(1)
            if raw:
                signals = {s.strip().lower() for s in raw.split(",") if s.strip()}
                suppressions[(finfo.path.as_posix(), line_no)] = signals
            else:
                suppressions[(finfo.path.as_posix(), line_no)] = None

    return suppressions


def filter_findings(
    findings: list[Finding],
    suppressions: Mapping[tuple[str, int], set[str] | None],
) -> tuple[list[Finding], list[Finding]]:
    """Partition findings into *active* and *suppressed*.

    A finding is suppressed when its ``(file_path, start_line)`` has a
    matching entry in *suppressions* that either covers all signals
    (``None``) or includes the finding's signal type.
    """
    if not suppressions:
        return findings, []

    active: list[Finding] = []
    suppressed: list[Finding] = []

    for f in findings:
        if f.file_path is None or f.start_line is None:
            active.append(f)
            continue

        key = (f.file_path.as_posix(), f.start_line)
        entry = suppressions.get(key)
        if entry is None and key not in suppressions:
            active.append(f)
        elif entry is None:
            # None entry means suppress ALL signals on this line
            suppressed.append(f)
        elif f.signal_type.value in entry:
            suppressed.append(f)
        else:
            active.append(f)

    return active, suppressed
