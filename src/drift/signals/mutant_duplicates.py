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


def _function_body_text(
    func: FunctionInfo, repo_path: Path, _cache: dict[Path, list[str]] | None = None
) -> str:
    """Read the function body from disk. Uses an optional line cache to avoid redundant I/O."""
    try:
        full = repo_path / func.file_path
        if _cache is not None:
            if full not in _cache:
                _cache[full] = full.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            lines = _cache[full]
        else:
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

        # Resolve similarity threshold from config
        similarity_threshold = SIMILARITY_THRESHOLD
        if hasattr(config, "thresholds"):
            similarity_threshold = config.thresholds.similarity_threshold

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
        # Group functions by LOC bucket (±30%) to reduce comparison pairs
        sample = functions[:500] if len(functions) > 500 else functions
        file_cache: dict[Path, list[str]] = {}

        # Build LOC buckets: each function goes into a bucket keyed by (loc // 5)
        # Then only compare functions in the same or adjacent buckets.
        loc_buckets: dict[int, list[FunctionInfo]] = {}
        for fn in sample:
            bucket = fn.loc // 5
            loc_buckets.setdefault(bucket, []).append(fn)

        pairs_to_compare: list[tuple[FunctionInfo, FunctionInfo]] = []
        for bucket_key, bucket_fns in loc_buckets.items():
            # Intra-bucket pairs
            for a, b in combinations(bucket_fns, 2):
                pairs_to_compare.append((a, b))
            # Adjacent bucket pairs (bucket_key + 1 only, to avoid double-counting)
            if (bucket_key + 1) in loc_buckets:
                for a in bucket_fns:
                    for b in loc_buckets[bucket_key + 1]:
                        pairs_to_compare.append((a, b))

        for a, b in pairs_to_compare:
            key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
            if key in checked:
                continue

            text_a = _function_body_text(a, self._repo_path, file_cache)
            text_b = _function_body_text(b, self._repo_path, file_cache)

            sim = _structural_similarity(text_a, text_b)
            if sim >= similarity_threshold and sim < 1.0:
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
