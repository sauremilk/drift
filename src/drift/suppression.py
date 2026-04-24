"""Inline suppression support — ``# drift:ignore`` comments."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from drift.models import FileInfo, Finding, FindingStatus, SignalType

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

_SECURITY_SIGNALS = {
    SignalType.HARDCODED_SECRET.value,
    SignalType.MISSING_AUTHORIZATION.value,
    SignalType.INSECURE_DEFAULT.value,
}


@dataclass(frozen=True)
class InlineSuppression:
    """Structured representation of a single inline ``drift:ignore`` directive."""

    file_path: str
    line_number: int
    signals: set[str] | None
    until: date | None = None
    reason: str | None = None
    #: Short SHA-256 hash of the code content *when the suppression was written*.
    #: Present only when the ``hash:XXXXXXXX`` tag appears in the comment.
    stored_hash: str | None = None
    #: Short SHA-256 hash of the code content *as read right now*.
    #: Always computed during collection; ``None`` only if the line was unreadable.
    current_hash: str | None = None


@dataclass(frozen=True)
class SuppressionFilterResult:
    """Result payload for inline suppression filtering with metadata."""

    active: list[Finding]
    suppressed: list[Finding]
    expired_suppressions: list[InlineSuppression] = field(default_factory=list)


_UNTIL_PATTERN = re.compile(r"\buntil:(\d{4}-\d{2}-\d{2})\b")
_REASON_PATTERN = re.compile(r"\breason:(.+)$")
_HASH_PATTERN = re.compile(r"\bhash:([0-9a-f]{8})\b")


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


def _parse_stored_hash(text: str) -> str | None:
    """Parse optional ``hash:XXXXXXXX`` metadata from comment tail."""
    match = _HASH_PATTERN.search(text)
    return match.group(1) if match else None


def _code_content_hash(code: str) -> str:
    """Return the first 8 hex chars of SHA-256 of *code* (stripped)."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:8]


def _resolve_signal_tokens(raw: str, signal_abbrev: dict) -> set[str]:
    """Parse and resolve comma-separated signal tokens from a suppression directive."""
    resolved: set[str] = set()
    for token in raw.split(","):
        signal = token.strip()
        if not signal:
            continue
        abbrev = signal.upper()
        if abbrev in signal_abbrev:
            resolved.add(signal_abbrev[abbrev])
        else:
            resolved.add(signal.lower())
    return resolved


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
                signals = _resolve_signal_tokens(raw, SIGNAL_ABBREV)

            tail = line[match.end():]
            code_part = line[: match.start()]
            entries.append(
                InlineSuppression(
                    file_path=finfo.path.as_posix(),
                    line_number=line_no,
                    signals=signals,
                    until=_parse_until(tail),
                    reason=_parse_reason(tail),
                    stored_hash=_parse_stored_hash(tail),
                    current_hash=_code_content_hash(code_part),
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


def scan_suppression_entries(
    files: list[FileInfo],
    repo_path: Path,
) -> dict[tuple[str, int], InlineSuppression]:
    """Scan source files and return full suppression entries keyed by location."""
    suppressions: dict[tuple[str, int], InlineSuppression] = {}

    for entry in collect_inline_suppressions(files, repo_path):
        suppressions[(entry.file_path, entry.line_number)] = entry

    return suppressions


def apply_inline_suppressions(
    findings: list[Finding],
    files: list[FileInfo],
    repo_path: Path,
    *,
    today: date | None = None,
) -> SuppressionFilterResult:
    """Apply inline suppressions discovered from repository files."""
    suppressions = scan_suppression_entries(files, repo_path)
    return filter_findings_with_report(findings, suppressions, today=today)


def _entry_signals(entry: InlineSuppression | set[str] | None) -> set[str] | None:
    if isinstance(entry, InlineSuppression):
        return entry.signals
    return entry


def filter_findings(
    findings: list[Finding],
    suppressions: Mapping[tuple[str, int], InlineSuppression | set[str] | None],
    *,
    today: date | None = None,
) -> tuple[list[Finding], list[Finding]]:
    """Partition findings into *active* and *suppressed*.

    A finding is suppressed when any line in its ``[start_line, end_line]``
    range has a matching entry in *suppressions* that either covers all
    signals (``None``) or includes the finding's signal type.
    """
    result = filter_findings_with_report(findings, suppressions, today=today)
    return result.active, result.suppressed


def filter_findings_with_report(
    findings: list[Finding],
    suppressions: Mapping[tuple[str, int], InlineSuppression | set[str] | None],
    *,
    today: date | None = None,
) -> SuppressionFilterResult:
    """Partition findings and report suppressions that expired by ``until`` date."""
    if not suppressions:
        return SuppressionFilterResult(active=findings, suppressed=[])

    current_day = today or date.today()

    active: list[Finding] = []
    suppressed: list[Finding] = []
    expired_by_key: dict[tuple[str, int], InlineSuppression] = {}

    for f in findings:
        if f.file_path is None or f.start_line is None:
            active.append(f)
            continue

        end_line = f.end_line if f.end_line is not None else f.start_line
        start_line = min(f.start_line, end_line)
        end_line = max(f.start_line, end_line)

        is_suppressed = False
        broad_security_suppression = False
        suppression_line: int | None = None
        for line_no in range(start_line, end_line + 1):
            key = (f.file_path.as_posix(), line_no)
            entry = suppressions.get(key)
            if entry is None and key not in suppressions:
                continue

            if isinstance(entry, InlineSuppression):
                if entry.until is not None and entry.until < current_day:
                    expired_by_key.setdefault(key, entry)
                    continue
                signals = entry.signals
            else:
                signals = _entry_signals(entry)

            if signals is None or f.signal_type in signals:
                is_suppressed = True
                suppression_line = line_no
                if signals is None and str(f.signal_type) in _SECURITY_SIGNALS:
                    broad_security_suppression = True
                break

        if is_suppressed:
            f.status = FindingStatus.SUPPRESSED
            f.status_set_by = "inline_comment"
            f.status_reason = "Suppressed by drift:ignore comment"
            if broad_security_suppression:
                f.metadata["broad_security_suppression"] = True
                if suppression_line is not None:
                    f.metadata["suppression_line"] = suppression_line
            suppressed.append(f)
        else:
            f.status = FindingStatus.ACTIVE
            active.append(f)

    return SuppressionFilterResult(
        active=active,
        suppressed=suppressed,
        expired_suppressions=sorted(
            expired_by_key.values(),
            key=lambda e: (e.file_path, e.line_number),
        ),
    )


# ---------------------------------------------------------------------------
# Writing suppressions into source files
# ---------------------------------------------------------------------------

_COMMENT_PREFIX_BY_LANG: dict[str, str] = {
    "python": "#",
    "typescript": "//",
    "tsx": "//",
    "javascript": "//",
    "jsx": "//",
}


def _build_signal_to_abbrev() -> dict[str, str]:
    """Return a mapping from full signal name → abbreviation."""
    from drift.config import SIGNAL_ABBREV

    return {full: abbrev for abbrev, full in SIGNAL_ABBREV.items()}


def insert_suppression_comment(
    file_path: Path,
    line_number: int,
    signals: set[str] | None,
    *,
    until: date | None = None,
    reason: str | None = None,
    language: str = "python",
    include_hash: bool = False,
) -> None:
    """Append a ``drift:ignore`` comment to *line_number* in *file_path*.

    Modifies the file in-place using UTF-8 encoding.  *line_number* is
    1-based.  *signals* is a set of full signal names (e.g.
    ``{"architecture_violation"}``); pass ``None`` to suppress all signals.

    When *include_hash* is ``True``, a short SHA-256 hash of the current line
    content is embedded in the comment as ``hash:XXXXXXXX``.  This enables
    ``drift suppress list --check-stale`` to detect suppressions whose code
    context has changed since the suppression was created.
    """
    prefix = _COMMENT_PREFIX_BY_LANG.get(language, "#")

    # Build the ignore tag
    if signals:
        signal_to_abbrev = _build_signal_to_abbrev()
        abbrevs = sorted(
            signal_to_abbrev.get(s, s.upper()) for s in signals
        )
        tag = f"{prefix} drift:ignore[{','.join(abbrevs)}]"
    else:
        tag = f"{prefix} drift:ignore"

    if until is not None:
        tag += f" until:{until.isoformat()}"
    if reason:
        tag += f" reason:{reason}"

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    idx = line_number - 1
    line = lines[idx]
    # Strip existing trailing newline to append comment cleanly
    stripped = line.rstrip("\n").rstrip("\r")
    eol = line[len(stripped):]

    if include_hash:
        tag += f" hash:{_code_content_hash(stripped)}"

    lines[idx] = f"{stripped}  {tag}{eol}"
    file_path.write_text("".join(lines), encoding="utf-8")
