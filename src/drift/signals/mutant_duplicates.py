"""Signal 3: Mutant Duplicate Score (MDS).

Detects near-duplicate functions — code that looks structurally very
similar but differs in subtle ways, suggesting copy-paste-then-modify
patterns typical of AI generation across multiple sessions.

Optimization: Uses LOC-bucket pre-filtering and body_hash grouping to
avoid the O(n²) all-pairs comparison.  Pre-computed AST n-grams from the
parsing phase are used directly — no disk I/O or re-parsing required.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

# Threshold above which two functions are considered near-duplicates
SIMILARITY_THRESHOLD = 0.80

# Maximum number of detailed comparisons to perform per bucket
_MAX_COMPARISONS_PER_BUCKET = 500

# Maximum near-duplicate findings to report
_MAX_FINDINGS = 200


def _get_precomputed_ngrams(func: FunctionInfo) -> list[tuple[str, ...]] | None:
    """Retrieve pre-computed AST n-grams from FunctionInfo.ast_fingerprint.

    Returns None if n-grams were not pre-computed (e.g. non-Python files
    or functions parsed before n-gram computation was added).
    """
    raw = func.ast_fingerprint.get("ngrams")
    if raw is None:
        return None
    if not raw:
        return []
    # Convert from JSON-safe list[list[str]] to list[tuple[str, ...]]
    return [tuple(ng) for ng in raw]


def _structural_similarity(
    ngrams_a: list[tuple[str, ...]] | None,
    ngrams_b: list[tuple[str, ...]] | None,
) -> float:
    """Compute structural similarity from pre-computed AST n-gram lists.

    Returns 0.0 when either side has no n-grams.
    """
    if not ngrams_a or not ngrams_b:
        return 0.0

    # Cheap reject: if ngram set sizes differ by >3×, similarity < 0.5
    len_a, len_b = len(ngrams_a), len(ngrams_b)
    if len_a > 0 and len_b > 0:
        size_ratio = min(len_a, len_b) / max(len_a, len_b)
        if size_ratio < 0.33:
            return size_ratio  # guaranteed below threshold

    return _jaccard(ngrams_a, ngrams_b)


def _jaccard(a: list[tuple[str, ...]], b: list[tuple[str, ...]]) -> float:
    """Jaccard similarity over two multiset n-gram lists."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    set_a = defaultdict(int)
    set_b = defaultdict(int)
    for ng in a:
        set_a[ng] += 1
    for ng in b:
        set_b[ng] += 1

    all_keys = set(set_a) | set(set_b)
    intersection = sum(min(set_a[k], set_b[k]) for k in all_keys)
    union = sum(max(set_a[k], set_b[k]) for k in all_keys)
    return intersection / union if union else 0.0


@register_signal
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
        config: DriftConfig,
    ) -> list[Finding]:
        # Collect all functions with sufficient size
        functions: list[FunctionInfo] = []
        for pr in parse_results:
            for fn in pr.functions:
                if fn.loc >= 5:  # Ignore trivial functions
                    functions.append(fn)

        if len(functions) < 2:
            return []

        # Resolve similarity threshold from config (if provided)
        if hasattr(config, "thresholds"):
            pass

        findings: list[Finding] = []
        checked: set[tuple[str, str]] = set()

        # ---- Phase 1: Exact duplicates via body_hash (O(n)) ----
        hash_groups: dict[str, list[FunctionInfo]] = defaultdict(list)
        for fn in functions:
            if fn.body_hash:
                hash_groups[fn.body_hash].append(fn)

        for _h, group in hash_groups.items():
            if len(group) > 1:
                for a, b in combinations(group, 2):
                    key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
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
                            metadata={
                                "similarity": 1.0,
                                "body_hash": _h,
                                "function_a": a.name,
                                "function_b": b.name,
                                "file_a": a.file_path.as_posix(),
                                "file_b": b.file_path.as_posix(),
                            },
                        )
                    )

        # ---- Phase 2: Near-duplicates via LOC-bucket comparison ----
        # Use pre-computed AST ngrams from the parsing phase (no disk I/O).
        ngram_cache: dict[str, list[tuple[str, ...]] | None] = {}
        for fn in functions:
            fn_key = f"{fn.file_path}:{fn.name}:{fn.start_line}"
            ngram_cache[fn_key] = _get_precomputed_ngrams(fn)

        # Group functions into LOC buckets (bucket_size=10 lines) so we
        # only compare functions of approximately similar size.
        bucket_size = 10
        loc_buckets: dict[int, list[FunctionInfo]] = defaultdict(list)
        for fn in functions:
            bucket = fn.loc // bucket_size
            loc_buckets[bucket].append(fn)

        sorted_buckets = sorted(loc_buckets.keys())

        for i, bucket_key in enumerate(sorted_buckets):
            # Compare within this bucket AND with the adjacent bucket
            # to catch functions near bucket boundaries
            candidates = list(loc_buckets[bucket_key])
            if i + 1 < len(sorted_buckets) and sorted_buckets[i + 1] == bucket_key + 1:
                candidates.extend(loc_buckets[sorted_buckets[i + 1]])

            if len(candidates) < 2:
                continue

            # Cap comparisons per bucket group
            comparisons = 0
            for a, b in combinations(candidates, 2):
                if comparisons >= _MAX_COMPARISONS_PER_BUCKET:
                    break
                if len(findings) >= _MAX_FINDINGS:
                    break

                key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
                if key in checked:
                    continue

                # Quick filter: similar line count (within 50%)
                if a.loc > 0 and b.loc > 0:
                    ratio = min(a.loc, b.loc) / max(a.loc, b.loc)
                    if ratio < 0.5:
                        continue

                # Quick filter: same body_hash → already reported as exact dupe
                if a.body_hash and a.body_hash == b.body_hash:
                    continue

                comparisons += 1
                ng_a = ngram_cache.get(f"{a.file_path}:{a.name}:{a.start_line}")
                ng_b = ngram_cache.get(f"{b.file_path}:{b.name}:{b.start_line}")

                sim = _structural_similarity(ng_a, ng_b)
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
                            metadata={
                                "similarity": round(sim, 3),
                                "function_a": a.name,
                                "function_b": b.name,
                                "file_a": a.file_path.as_posix(),
                                "file_b": b.file_path.as_posix(),
                            },
                        )
                    )

            if len(findings) >= _MAX_FINDINGS:
                break

        return findings
