"""Signal 3: Mutant Duplicate Score (MDS).

Detects near-duplicate functions — code that looks structurally very
similar but differs in subtle ways, suggesting copy-paste-then-modify
patterns typical of AI generation across multiple sessions.
"""

from __future__ import annotations

import difflib
from itertools import combinations
from pathlib import Path
from typing import Any

from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal

# Threshold above which two functions are considered near-duplicates
SIMILARITY_THRESHOLD = 0.80


def _function_body_text(func: FunctionInfo, repo_path: Path) -> str:
    """Read the function body from disk. Returns empty string on failure."""
    try:
        full = repo_path / func.file_path
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[func.start_line - 1 : func.end_line])
    except Exception:
        return ""


def _structural_similarity(a: str, b: str) -> float:
    """Compute structural similarity using SequenceMatcher."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class MutantDuplicateSignal(BaseSignal):
    """Detect near-duplicate functions that diverge in subtle ways."""

    def __init__(self, repo_path: Path) -> None:
        self._repo_path = repo_path

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MUTANT_DUPLICATE

    @property
    def name(self) -> str:
        return "Mutant Duplicates"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        # Collect all functions with sufficient size
        functions: list[FunctionInfo] = []
        for pr in parse_results:
            for fn in pr.functions:
                if fn.loc >= 5:  # Ignore trivial functions
                    functions.append(fn)

        if len(functions) < 2:
            return []

        # Compare all pairs — O(n²) but acceptable for typical repos (< 5000 functions)
        # For large repos (>5k functions), body_hash pre-filtering reduces comparisons
        findings: list[Finding] = []
        checked: set[tuple[str, str]] = set()

        # Pre-filter: group by body hash for exact duplicates
        hash_groups: dict[str, list[FunctionInfo]] = {}
        for fn in functions:
            if fn.body_hash:
                hash_groups.setdefault(fn.body_hash, []).append(fn)

        # Report exact duplicates
        for h, group in hash_groups.items():
            if len(group) > 1:
                for a, b in combinations(group, 2):
                    key = tuple(
                        sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"])
                    )
                    if key in checked:
                        continue
                    checked.add(key)

                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.HIGH,
                            score=0.9,
                            title=f"Exact duplicate: {a.name} ↔ {b.name}",
                            description=(
                                f"{a.file_path}:{a.start_line} and "
                                f"{b.file_path}:{b.start_line} are identical "
                                f"({a.loc} lines). Consider consolidating."
                            ),
                            file_path=a.file_path,
                            start_line=a.start_line,
                            related_files=[b.file_path],
                            metadata={"similarity": 1.0, "body_hash": h},
                        )
                    )

        # Near-duplicate detection via body text comparison
        # Sample up to 500 functions to keep analysis time bounded
        sample = functions[:500] if len(functions) > 500 else functions

        for a, b in combinations(sample, 2):
            key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
            if key in checked:
                continue

            # Quick filter: similar line count
            if a.loc > 0 and b.loc > 0:
                ratio = min(a.loc, b.loc) / max(a.loc, b.loc)
                if ratio < 0.5:
                    continue

            text_a = _function_body_text(a, self._repo_path)
            text_b = _function_body_text(b, self._repo_path)

            sim = _structural_similarity(text_a, text_b)
            if sim >= SIMILARITY_THRESHOLD and sim < 1.0:
                checked.add(key)

                severity = Severity.MEDIUM if sim < 0.9 else Severity.HIGH
                score = sim * 0.85  # Scale to leave room for exact dupes

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=score,
                        title=f"Near-duplicate ({sim:.0%}): {a.name} ↔ {b.name}",
                        description=(
                            f"{a.file_path}:{a.start_line} and "
                            f"{b.file_path}:{b.start_line} are {sim:.0%} similar. "
                            f"Small differences may indicate copy-paste divergence."
                        ),
                        file_path=a.file_path,
                        start_line=a.start_line,
                        related_files=[b.file_path],
                        metadata={"similarity": round(sim, 3)},
                    )
                )

        return findings

    def score(self, findings: list[Finding]) -> float:
        if not findings:
            return 0.0
        return min(1.0, sum(f.score for f in findings) / max(len(findings), 2))
