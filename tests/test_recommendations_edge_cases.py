"""Tests for recommendations engine: all code paths and edge cases.

Targeted gaps (recommendations.py at 86%):
- PFS recommender returning None when variant_count < 2 (line 35)
- AVS recommender returning None for unrecognized title (lines 78-93)
- EDS recommender returning None when no suggestions (line 153)
- TVS with low AI ratio and low churn
- SMS with empty novel_deps falling back to novel_dependencies key
- Doc-impl-drift signal type has no recommender → skipped entirely
- generate_recommendations: deduplication, sorting, max limit edge

These matter because recommendations guide user action — a missing
recommendation for a valid finding is a silent failure.
"""

from pathlib import Path

from drift.models import Finding, Severity, SignalType
from drift.recommendations import (
    _recommend_architecture_violation,
    _recommend_explainability_deficit,
    _recommend_pattern_fragmentation,
    _recommend_system_misalignment,
    _recommend_temporal_volatility,
    generate_recommendations,
)


def _make_finding(
    signal: SignalType,
    score: float = 0.5,
    title: str = "test finding",
    metadata: dict | None = None,
    file_path: Path | None = None,
    related_files: list[Path] | None = None,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.MEDIUM,
        score=score,
        title=title,
        description="test description",
        file_path=file_path or Path("src/module.py"),
        metadata=metadata or {},
        related_files=related_files or [],
    )


class TestPatternFragmentationEdgeCases:
    def test_variant_count_below_two_returns_none(self):
        """PFS with < 2 variants → no recommendation (line 35)."""
        finding = _make_finding(
            SignalType.PATTERN_FRAGMENTATION,
            metadata={"variant_count": 1, "canonical_variant": "x", "module": "src"},
        )
        rec = _recommend_pattern_fragmentation(finding)
        assert rec is None

    def test_variant_count_zero_returns_none(self):
        finding = _make_finding(
            SignalType.PATTERN_FRAGMENTATION,
            metadata={"variant_count": 0},
        )
        rec = _recommend_pattern_fragmentation(finding)
        assert rec is None

    def test_many_related_files_truncated(self):
        """More than 3 related files → '+N more' suffix."""
        files = [Path(f"src/f{i}.py") for i in range(6)]
        finding = _make_finding(
            SignalType.PATTERN_FRAGMENTATION,
            metadata={"variant_count": 5, "canonical_variant": "try-except", "module": "src"},
            related_files=files,
        )
        rec = _recommend_pattern_fragmentation(finding)
        assert rec is not None
        assert "+3 more" in rec.description

    def test_no_related_files_shows_question_mark(self):
        finding = _make_finding(
            SignalType.PATTERN_FRAGMENTATION,
            metadata={"variant_count": 3, "canonical_variant": "x", "module": "mod"},
            related_files=[],
        )
        rec = _recommend_pattern_fragmentation(finding)
        assert rec is not None
        assert "?" in rec.description


class TestArchitectureViolationEdgeCases:
    def test_unrecognized_title_returns_none(self):
        """AVS finding with title not containing 'circular'/'upward'/'layer' → None."""
        finding = _make_finding(
            SignalType.ARCHITECTURE_VIOLATION,
            title="Hub module exceeds coupling threshold",
            metadata={},
        )
        rec = _recommend_architecture_violation(finding)
        assert rec is None

    def test_upward_import_recommendation(self):
        finding = _make_finding(
            SignalType.ARCHITECTURE_VIOLATION,
            title="Upward import from db to api",
            metadata={},
        )
        rec = _recommend_architecture_violation(finding)
        assert rec is not None
        assert "upward" in rec.title.lower() or "layer" in rec.title.lower()

    def test_layer_violation_recommendation(self):
        finding = _make_finding(
            SignalType.ARCHITECTURE_VIOLATION,
            title="Cross-layer dependency detected",
            metadata={},
        )
        rec = _recommend_architecture_violation(finding)
        assert rec is not None


class TestExplainabilityDeficitEdgeCases:
    def test_all_present_returns_none(self):
        """Function with docstring, types, low complexity → no recommendation."""
        finding = _make_finding(
            SignalType.EXPLAINABILITY_DEFICIT,
            metadata={
                "function_name": "simple_func",
                "complexity": 3,
                "has_docstring": True,
                "has_return_type": True,
            },
        )
        rec = _recommend_explainability_deficit(finding)
        assert rec is None

    def test_high_complexity_suggests_split(self):
        finding = _make_finding(
            SignalType.EXPLAINABILITY_DEFICIT,
            metadata={
                "function_name": "complex_func",
                "complexity": 15,
                "has_docstring": True,
                "has_return_type": True,
            },
        )
        rec = _recommend_explainability_deficit(finding)
        assert rec is not None
        assert "split" in rec.description.lower() or "complexity" in rec.description.lower()

    def test_missing_return_type_only(self):
        finding = _make_finding(
            SignalType.EXPLAINABILITY_DEFICIT,
            metadata={
                "function_name": "func",
                "complexity": 3,
                "has_docstring": True,
                "has_return_type": False,
            },
        )
        rec = _recommend_explainability_deficit(finding)
        assert rec is not None
        assert "return type" in rec.description.lower()


class TestTemporalVolatilityEdgeCases:
    def test_low_ai_ratio_low_churn(self):
        """Even with low metrics, integration test advice is always added."""
        finding = _make_finding(
            SignalType.TEMPORAL_VOLATILITY,
            metadata={"ai_ratio": 0.1, "change_frequency_30d": 0.5},
            file_path=Path("src/stable.py"),
        )
        rec = _recommend_temporal_volatility(finding)
        assert rec is not None
        assert "integration" in rec.description.lower() or "test" in rec.description.lower()


class TestSystemMisalignmentEdgeCases:
    def test_fallback_to_novel_dependencies_key(self):
        """When novel_imports is empty, falls back to novel_dependencies."""
        finding = _make_finding(
            SignalType.SYSTEM_MISALIGNMENT,
            metadata={"novel_imports": [], "novel_dependencies": ["redis"]},
        )
        rec = _recommend_system_misalignment(finding)
        assert rec is not None
        assert "redis" in rec.description

    def test_empty_both_keys_still_generates(self):
        """Even with no deps listed, still generates a recommendation."""
        finding = _make_finding(
            SignalType.SYSTEM_MISALIGNMENT,
            metadata={},
        )
        rec = _recommend_system_misalignment(finding)
        assert rec is not None


class TestDocImplDriftNoRecommender:
    def test_doc_impl_drift_skipped(self):
        """DOC_IMPL_DRIFT has no recommender → finding produces no rec."""
        finding = _make_finding(
            SignalType.DOC_IMPL_DRIFT,
            score=0.8,
            metadata={},
        )
        recs = generate_recommendations([finding])
        assert recs == []


class TestGenerateRecommendationsEdgeCases:
    def test_max_recommendations_exactly_reached(self):
        """Exactly max_recommendations findings → exactly that many recs."""
        findings = [
            _make_finding(
                SignalType.MUTANT_DUPLICATE,
                score=0.5 + i * 0.01,
                title=f"dup {i}",
                metadata={
                    "function_a": f"fa_{i}",
                    "function_b": f"fb_{i}",
                    "similarity": 0.9,
                    "file_a": "a.py",
                    "file_b": "b.py",
                },
            )
            for i in range(3)
        ]
        recs = generate_recommendations(findings, max_recommendations=3)
        assert len(recs) == 3

    def test_mixed_signal_types_sorted(self):
        """Findings from different signals produce correctly sorted recs."""
        findings = [
            _make_finding(
                SignalType.EXPLAINABILITY_DEFICIT,
                score=0.3,
                metadata={
                    "function_name": "f",
                    "complexity": 3,
                    "has_docstring": False,
                    "has_return_type": True,
                },
            ),
            _make_finding(
                SignalType.ARCHITECTURE_VIOLATION,
                score=0.9,
                title="Circular dependency detected",
                metadata={"cycle": ["a", "b"]},
            ),
        ]
        recs = generate_recommendations(findings)
        # High-impact recs come first
        assert recs[0].impact == "high"
