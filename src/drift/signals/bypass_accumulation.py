"""Signal 12: Bypass Accumulation Tracker (BAT).

Detects files or modules where quality-bypass markers (``# type: ignore``,
``# noqa``, ``# pragma: no cover``, ``typing.Any`` annotations, ``cast()``,
``@pytest.mark.skip``, ``TODO``/``FIXME``/``HACK``/``XXX``) accumulate
beyond a density threshold.

High bypass density is a proxy for *process drift*: the gap between the
quality process a team intends and the shortcuts actually taken.
"""

from __future__ import annotations

import re
from pathlib import Path
from statistics import median

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

# ── Bypass marker patterns ────────────────────────────────────────

_MARKER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("type_safety", re.compile(r"#\s*type:\s*ignore")),
    ("lint", re.compile(r"#\s*noqa\b")),
    ("coverage", re.compile(r"#\s*pragma:\s*no\s*cover")),
    ("type_safety", re.compile(r"\bcast\s*\(")),
    ("test", re.compile(r"pytest\.mark\.skip")),
    ("deferred", re.compile(r"#\s*(?:TODO|FIXME|HACK|XXX)\b")),
]

# typing.Any in function annotations — checked structurally
_ANY_ANNOTATION = re.compile(r"\bAny\b")


def _is_test_file(file_path: Path) -> bool:
    name = file_path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _count_markers(source: str) -> dict[str, int]:
    """Count bypass markers in source text, grouped by category."""
    counts: dict[str, int] = {
        "type_safety": 0,
        "lint": 0,
        "coverage": 0,
        "test": 0,
        "deferred": 0,
    }
    for line in source.splitlines():
        for category, pattern in _MARKER_PATTERNS:
            if pattern.search(line):
                counts[category] += 1
    return counts


def _count_any_annotations(pr: ParseResult) -> int:
    """Count typing.Any usage in function parameter/return annotations."""
    count = 0
    for fn in pr.functions:
        if fn.return_type and _ANY_ANNOTATION.search(fn.return_type):
            count += 1
        for param in fn.parameters:
            ptype = param.get("type", "") if isinstance(param, dict) else ""
            if ptype and _ANY_ANNOTATION.search(ptype):
                count += 1
    return count


def _read_file_source(
    file_path: Path, repo_path: Path | None = None,
) -> str | None:
    """Read full file source."""
    try:
        target = file_path
        if repo_path and not file_path.is_absolute():
            target = repo_path / file_path
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _total_loc(pr: ParseResult) -> int:
    """Estimate total LOC from function LOCs or file read."""
    return sum(fn.loc for fn in pr.functions) if pr.functions else 0


@register_signal
class BypassAccumulationSignal(BaseSignal):
    """Detect files with abnormally high density of quality-bypass markers."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BYPASS_ACCUMULATION

    @property
    def name(self) -> str:
        return "Bypass Accumulation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        density_threshold = config.thresholds.bat_density_threshold
        min_loc = config.thresholds.bat_min_loc
        findings: list[Finding] = []

        # Phase 1: collect per-file bypass densities
        file_data: list[tuple[ParseResult, dict[str, int], int, float, int]] = []

        for pr in parse_results:
            if pr.language != "python":
                continue
            if _is_test_file(pr.file_path):
                continue

            source = _read_file_source(pr.file_path, self._repo_path)
            if source is None:
                continue

            loc = source.count("\n") + 1
            if loc < min_loc:
                continue

            markers = _count_markers(source)
            markers["type_safety"] += _count_any_annotations(pr)

            total = sum(markers.values())
            if total == 0:
                continue

            density = total / loc
            file_data.append((pr, markers, total, density, loc))

        if not file_data:
            return findings

        # Phase 2: compute median density for anomaly context
        densities = [d for _, _, _, d, _ in file_data]
        median_density = median(densities) if densities else 0.0

        # Phase 3: emit findings for files above threshold
        for pr, markers, total, density, file_loc in file_data:
            if density < density_threshold:
                continue

            score = min(1.0, density / density_threshold)
            severity = (
                Severity.HIGH if density >= density_threshold * 2
                else Severity.MEDIUM
            )

            # Build category breakdown for description
            categories = {k: v for k, v in markers.items() if v > 0}
            cat_desc = ", ".join(
                f"{k}: {v}" for k, v in sorted(
                    categories.items(), key=lambda x: -x[1],
                )
            )

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=f"High bypass marker density in {pr.file_path.name}",
                    description=(
                        f"{pr.file_path} has {total} bypass markers "
                        f"across ~{file_loc} LOC "
                        f"(density {density:.3f}, threshold {density_threshold:.3f}). "
                        f"Breakdown: {cat_desc}."
                    ),
                    file_path=pr.file_path,
                    start_line=1,
                    end_line=None,
                    fix=(
                        f"Review bypass markers in '{pr.file_path.name}' and "
                        f"resolve the underlying issues they suppress. "
                        f"Each marker represents a quality shortcut that "
                        f"may mask real problems."
                    ),
                    metadata={
                        "total_markers": total,
                        "markers_by_category": markers,
                        "bypass_density": round(density, 4),
                        "module_median_density": round(median_density, 4),
                    },
                )
            )

        return findings
