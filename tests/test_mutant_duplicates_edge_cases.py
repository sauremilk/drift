"""Tests for mutant_duplicates signal: edge cases, exact duplicates, limits.

Targeted gaps (mutant_duplicates.py at 64%):
- Exact duplicate grouping (hash-based, Phase 1)
- LOC ratio filter (< 0.5 → skip pair)
- Dunder method exclusion
- _structural_similarity: size ratio check, empty ngrams
- _jaccard: both empty → 1.0, one empty → 0.0
- _get_precomputed_ngrams: None vs empty
- Max findings limit

These tests matter because MDS is one of the highest-impact signals
and false positives here reduce trust in the entire analysis.
"""

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import FunctionInfo, ParseResult
from drift.signals.mutant_duplicates import (
    MutantDuplicateSignal,
    _get_precomputed_ngrams,
    _is_package_lazy_getattr,
    _jaccard,
    _structural_similarity,
)

# ── _jaccard ──────────────────────────────────────────────────────────────


class TestJaccard:
    def test_identical_ngrams(self):
        ng = [("a", "b"), ("c", "d")]
        assert _jaccard(ng, ng) == 1.0

    def test_completely_different(self):
        a = [("a", "b")]
        b = [("c", "d")]
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = [("a", "b"), ("c", "d")]
        b = [("a", "b"), ("e", "f")]
        sim = _jaccard(a, b)
        assert 0.0 < sim < 1.0
        # Jaccard = 1 / 3 = 0.333...
        assert abs(sim - 1 / 3) < 0.01

    def test_both_empty(self):
        """Two empty lists → identical (similarity 1.0)."""
        assert _jaccard([], []) == 1.0

    def test_one_empty(self):
        """One empty, one non-empty → 0.0."""
        assert _jaccard([], [("a",)]) == 0.0
        assert _jaccard([("a",)], []) == 0.0

    def test_multiset_handles_duplicates(self):
        """Repeated n-grams are counted with multiplicity."""
        a = [("a",), ("a",), ("b",)]
        b = [("a",), ("b",), ("b",)]
        # min intersection: a→1, b→1 = 2; max union: a→2, b→2 = 4
        sim = _jaccard(a, b)
        assert abs(sim - 0.5) < 0.01


# ── _structural_similarity ───────────────────────────────────────────────


class TestStructuralSimilarity:
    def test_none_ngrams_returns_zero(self):
        assert _structural_similarity(None, [("a",)]) == 0.0
        assert _structural_similarity([("a",)], None) == 0.0
        assert _structural_similarity(None, None) == 0.0

    def test_empty_ngrams_returns_zero(self):
        assert _structural_similarity([], [("a",)]) == 0.0
        assert _structural_similarity([("a",)], []) == 0.0

    def test_identical_returns_one(self):
        ng = [("a", "b"), ("c", "d"), ("e", "f")]
        assert _structural_similarity(ng, ng) == 1.0

    def test_size_ratio_below_threshold_returns_ratio(self):
        """When size ratio < 0.33, returns the ratio directly (early exit)."""
        small = [("a",)]
        large = [("a",), ("b",), ("c",), ("d",)]  # ratio = 1/4 = 0.25
        sim = _structural_similarity(small, large)
        assert sim == pytest.approx(0.25, abs=0.01)

    def test_moderate_size_difference_uses_jaccard(self):
        """Size ratio >= 0.33 → falls through to Jaccard."""
        a = [("a",), ("b",), ("c",)]
        b = [("a",), ("b",), ("c",), ("d",), ("e",)]  # ratio 3/5 = 0.6
        sim = _structural_similarity(a, b)
        assert sim > 0.0


# ── _get_precomputed_ngrams ──────────────────────────────────────────────


class TestGetPrecomputedNgrams:
    def test_none_fingerprint(self):
        fn = FunctionInfo(
            name="f",
            start_line=1,
            end_line=5,
            loc=5,
            complexity=1,
            file_path=Path("a.py"),
            language="python",
            ast_fingerprint={},
        )
        assert _get_precomputed_ngrams(fn) is None

    def test_empty_ngrams_list(self):
        fn = FunctionInfo(
            name="f",
            start_line=1,
            end_line=5,
            loc=5,
            complexity=1,
            file_path=Path("a.py"),
            language="python",
            ast_fingerprint={"ngrams": []},
        )
        assert _get_precomputed_ngrams(fn) == []

    def test_converts_lists_to_tuples(self):
        fn = FunctionInfo(
            name="f",
            start_line=1,
            end_line=5,
            loc=5,
            complexity=1,
            file_path=Path("a.py"),
            language="python",
            ast_fingerprint={"ngrams": [["a", "b"], ["c", "d"]]},
        )
        result = _get_precomputed_ngrams(fn)
        assert result == [("a", "b"), ("c", "d")]

    def test_ngrams_none_value(self):
        fn = FunctionInfo(
            name="f",
            start_line=1,
            end_line=5,
            loc=5,
            complexity=1,
            file_path=Path("a.py"),
            language="python",
            ast_fingerprint={"ngrams": None},
        )
        assert _get_precomputed_ngrams(fn) is None


# ── Dunder method exclusion ──────────────────────────────────────────────


class TestDunderExclusion:
    """Dunder methods should be excluded from MDS because they're
    intentionally similar (Protocol implementations)."""

    def test_dunder_methods_in_exclusion_set(self):
        from drift.signals.mutant_duplicates import _DUNDER_METHODS

        # Spot-check critical dunder methods
        assert "__eq__" in _DUNDER_METHODS
        assert "__hash__" in _DUNDER_METHODS
        assert "__repr__" in _DUNDER_METHODS
        assert "__enter__" in _DUNDER_METHODS
        assert "__exit__" in _DUNDER_METHODS
        assert "__getitem__" in _DUNDER_METHODS

    def test_non_dunder_not_in_set(self):
        from drift.signals.mutant_duplicates import _DUNDER_METHODS

        assert "process_data" not in _DUNDER_METHODS
        assert "__init__" not in _DUNDER_METHODS  # __init__ is NOT excluded


# ── MDS constants ─────────────────────────────────────────────────────────


def test_max_findings_limit_is_reasonable():
    from drift.signals.mutant_duplicates import _MAX_FINDINGS

    assert _MAX_FINDINGS > 0
    assert _MAX_FINDINGS <= 1000


def test_max_comparisons_prevents_quadratic():
    from drift.signals.mutant_duplicates import _MAX_COMPARISONS_PER_BUCKET

    assert _MAX_COMPARISONS_PER_BUCKET > 0
    assert _MAX_COMPARISONS_PER_BUCKET <= 5000


def test_similarity_threshold_in_valid_range():
    from drift.signals.mutant_duplicates import SIMILARITY_THRESHOLD

    assert 0.5 <= SIMILARITY_THRESHOLD <= 1.0


# ── Package lazy __getattr__ suppression ───────────────────────────────────


def _make_fn(
    *,
    name: str,
    file_path: str,
    body_hash: str,
    ngrams: list[list[str]],
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        start_line=1,
        end_line=7,
        loc=7,
        complexity=2,
        file_path=Path(file_path),
        language="python",
        body_hash=body_hash,
        ast_fingerprint={"ngrams": ngrams},
    )


def test_is_package_lazy_getattr_helper():
    package_fn = _make_fn(
        name="__getattr__",
        file_path="pkg_a/__init__.py",
        body_hash="h1",
        ngrams=[["Name", "Load"], ["If", "Return"]],
    )
    module_fn = _make_fn(
        name="__getattr__",
        file_path="pkg_a/exports.py",
        body_hash="h2",
        ngrams=[["Name", "Load"], ["If", "Return"]],
    )

    assert _is_package_lazy_getattr(package_fn) is True
    assert _is_package_lazy_getattr(module_fn) is False


def test_analyze_skips_package_init_getattr_duplicates():
    signal = MutantDuplicateSignal()
    config = DriftConfig()
    ngrams = [["Name", "Load"], ["If", "Return"], ["Raise", "NameError"]]

    pr_a = ParseResult(
        file_path=Path("pkg_a/__init__.py"),
        language="python",
        functions=[
            _make_fn(
                name="__getattr__",
                file_path="pkg_a/__init__.py",
                body_hash="lazy_hash",
                ngrams=ngrams,
            )
        ],
    )
    pr_b = ParseResult(
        file_path=Path("pkg_b/__init__.py"),
        language="python",
        functions=[
            _make_fn(
                name="__getattr__",
                file_path="pkg_b/__init__.py",
                body_hash="lazy_hash",
                ngrams=ngrams,
            )
        ],
    )

    findings = signal.analyze([pr_a, pr_b], {}, config)
    assert findings == []


def test_analyze_keeps_non_init_getattr_duplicates_detectable():
    signal = MutantDuplicateSignal()
    config = DriftConfig()
    ngrams = [["Name", "Load"], ["If", "Return"], ["Raise", "NameError"]]

    pr_a = ParseResult(
        file_path=Path("pkg_a/exports.py"),
        language="python",
        functions=[
            _make_fn(
                name="__getattr__",
                file_path="pkg_a/exports.py",
                body_hash="dup_hash",
                ngrams=ngrams,
            )
        ],
    )
    pr_b = ParseResult(
        file_path=Path("pkg_b/exports.py"),
        language="python",
        functions=[
            _make_fn(
                name="__getattr__",
                file_path="pkg_b/exports.py",
                body_hash="dup_hash",
                ngrams=ngrams,
            )
        ],
    )

    findings = signal.analyze([pr_a, pr_b], {}, config)
    assert len(findings) == 1
    assert findings[0].severity.value == "high"
    assert findings[0].metadata.get("group_size") == 2
