"""Tests for Pattern Fragmentation signal."""

from pathlib import Path

from drift.models import (
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.signals.pattern_fragmentation import PatternFragmentationSignal


def _make_pattern(
    category: PatternCategory,
    module: str,
    func: str,
    fingerprint: dict,
    line: int = 1,
) -> PatternInstance:
    return PatternInstance(
        category=category,
        file_path=Path(f"{module}/{func}.py"),
        function_name=func,
        start_line=line,
        end_line=line + 5,
        fingerprint=fingerprint,
    )


def _wrap(patterns: list[PatternInstance]) -> list[ParseResult]:
    """Wrap PatternInstances into a minimal ParseResult list."""
    return [
        ParseResult(
            file_path=Path("dummy.py"),
            language="python",
            patterns=patterns,
        )
    ]


def test_no_patterns_returns_no_findings():
    signal = PatternFragmentationSignal()
    findings = signal.analyze(_wrap([]), {}, None)
    assert findings == []


def test_single_variant_no_fragmentation():
    # All patterns in one module use the same fingerprint → no fragmentation
    patterns = [
        _make_pattern(
            PatternCategory.ERROR_HANDLING,
            "services",
            f"func_{i}",
            {
                "handler_count": 1,
                "handlers": [{"exception_type": "ValueError", "actions": ["raise"]}],
            },
        )
        for i in range(4)
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert findings == []


def test_two_variants_detected():
    fp_a = {
        "handler_count": 1,
        "handlers": [{"exception_type": "ValueError", "actions": ["raise"]}],
    }
    fp_b = {
        "handler_count": 1,
        "handlers": [{"exception_type": "Exception", "actions": ["print"]}],
    }

    patterns = [
        _make_pattern(PatternCategory.ERROR_HANDLING, "services", "func_a", fp_a),
        _make_pattern(PatternCategory.ERROR_HANDLING, "services", "func_b", fp_a),
        _make_pattern(PatternCategory.ERROR_HANDLING, "services", "func_c", fp_b),
    ]

    signal = PatternFragmentationSignal()
    findings = signal.analyze(_wrap(patterns), {}, None)

    assert len(findings) == 1
    f = findings[0]
    assert f.signal_type == SignalType.PATTERN_FRAGMENTATION
    assert f.metadata["num_variants"] == 2
    assert f.metadata["total_instances"] == 3
    assert f.metadata["canonical_count"] == 2  # fp_a used twice
    assert 0.4 <= f.score <= 0.6  # 1 - 1/2 = 0.5
    assert f.fix is not None
    assert "Consolidate to the dominant pattern" in f.fix
    assert "exemplar:" in f.fix
    assert "Deviations:" in f.fix
    assert ".py:" in f.fix
    assert "Konsolidiere" not in f.fix


def test_three_variants_higher_score():
    fps = [
        {"h": [{"type": "ValueError", "act": ["raise"]}]},
        {"h": [{"type": "Exception", "act": ["print"]}]},
        {"h": [{"type": "OSError", "act": ["log"]}]},
    ]
    patterns = [
        _make_pattern(PatternCategory.ERROR_HANDLING, "core", f"f{i}", fp)
        for i, fp in enumerate(fps)
    ]

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    # 1 - 1/3 ≈ 0.667
    assert findings[0].score > 0.6


def test_separate_modules_separate_findings():
    fp_a = {"x": 1}
    fp_b = {"x": 2}

    patterns = [
        _make_pattern(PatternCategory.ERROR_HANDLING, "mod_a", "f1", fp_a),
        _make_pattern(PatternCategory.ERROR_HANDLING, "mod_a", "f2", fp_b),
        _make_pattern(PatternCategory.ERROR_HANDLING, "mod_b", "f3", fp_a),
        _make_pattern(PatternCategory.ERROR_HANDLING, "mod_b", "f4", fp_b),
    ]

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    # Two modules × 1 category = 2 findings
    assert len(findings) == 2


def test_identical_decorator_patterns_no_finding():
    # 5 FastAPI-style routes with identical fingerprints (same structure, different
    # paths/methods) must produce no PFS finding — structural similarity here comes
    # from the framework pattern, not from fragmented logic.
    fp = {
        "has_error_handling": False,
        "has_auth": False,
        "auth_mechanism": None,
        "return_patterns": ["jsonify"],
    }
    patterns = [
        _make_pattern(PatternCategory.API_ENDPOINT, "routes", f"route_{i}", fp)
        for i in range(5)
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert findings == [], "Identical decorator patterns must not produce any PFS finding"


def test_score_aggregation():
    findings = [
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="a",
            description="",
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.7,
            title="b",
            description="",
        ),
    ]
    avg_score = sum(f.score for f in findings) / len(findings)
    assert avg_score == 0.6
