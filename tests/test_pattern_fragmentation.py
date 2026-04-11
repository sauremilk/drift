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


def test_framework_surface_error_handling_is_dampened():
    fps = [
        {"handler": "value_error"},
        {"handler": "exception"},
        {"handler": "os_error"},
        {"handler": "type_error"},
        {"handler": "runtime_error"},
    ]
    patterns = [
        _make_pattern(PatternCategory.ERROR_HANDLING, "backend/api/routers", f"f{i}", fp)
        for i, fp in enumerate(fps)
    ]

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.score < 0.7
    assert finding.severity == Severity.MEDIUM
    assert finding.metadata["framework_context_dampened"] is True
    assert finding.metadata["framework_context_hints"]


def test_core_error_handling_is_not_dampened():
    fps = [
        {"handler": "value_error"},
        {"handler": "exception"},
        {"handler": "os_error"},
        {"handler": "type_error"},
        {"handler": "runtime_error"},
    ]
    patterns = [
        _make_pattern(PatternCategory.ERROR_HANDLING, "core/domain", f"f{i}", fp)
        for i, fp in enumerate(fps)
    ]

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.score >= 0.7
    assert finding.severity == Severity.HIGH
    assert finding.metadata["framework_context_dampened"] is False
    assert finding.metadata["framework_context_hints"] == []


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
        _make_pattern(PatternCategory.API_ENDPOINT, "routes", f"route_{i}", fp) for i in range(5)
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert findings == [], "Identical decorator patterns must not produce any PFS finding"


def test_plugin_architecture_api_fragmentation_is_dampened_to_low():
    # Plugin/extension layouts intentionally vary across plugin boundaries.
    # High-severity PFS should be dampened for extension-specific API surfaces.
    target_fingerprints = [
        {"route": "send-message"},
        {"route": "send-media"},
        {"route": "edit-message"},
        {"route": "delete-message"},
        {"route": "pin-message"},
    ]
    patterns = [
        _make_pattern(PatternCategory.API_ENDPOINT, "extensions/bluebubbles/src", f"f{i}", fp)
        for i, fp in enumerate(target_fingerprints)
    ]
    patterns.extend(
        [
            _make_pattern(
                PatternCategory.API_ENDPOINT,
                "extensions/discord/src",
                "discord_route",
                {"route": "send-message"},
            ),
            _make_pattern(
                PatternCategory.API_ENDPOINT,
                "extensions/whatsapp/src",
                "whatsapp_route",
                {"route": "send-message"},
            ),
        ]
    )

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path.as_posix() == "extensions/bluebubbles/src"
    assert finding.severity == Severity.LOW
    assert finding.metadata["plugin_context_dampened"] is True
    assert finding.metadata["plugin_context_hints"]


def test_combined_framework_and_plugin_dampening_caps_to_info():
    # Error-handling variants inside one extension API surface can be expected
    # when several plugins expose distinct external-provider contracts.
    error_fingerprints = [
        {"handler": "value_error"},
        {"handler": "exception"},
        {"handler": "os_error"},
        {"handler": "type_error"},
        {"handler": "runtime_error"},
    ]
    patterns = [
        _make_pattern(
            PatternCategory.ERROR_HANDLING,
            "extensions/anthropic/src/api",
            f"err_{i}",
            fp,
        )
        for i, fp in enumerate(error_fingerprints)
    ]
    patterns.extend(
        [
            _make_pattern(
                PatternCategory.ERROR_HANDLING,
                "extensions/openai/src/api",
                "openai_err",
                {"handler": "provider_specific"},
            ),
            _make_pattern(
                PatternCategory.ERROR_HANDLING,
                "extensions/sglang/src/api",
                "sglang_err",
                {"handler": "provider_specific"},
            ),
        ]
    )
    patterns.extend(
        [
            _make_pattern(
                PatternCategory.API_ENDPOINT,
                "extensions/anthropic/src/api",
                "route_a",
                {"route": "messages"},
            ),
            _make_pattern(
                PatternCategory.API_ENDPOINT,
                "extensions/openai/src/api",
                "route_b",
                {"route": "chat"},
            ),
            _make_pattern(
                PatternCategory.API_ENDPOINT,
                "extensions/sglang/src/api",
                "route_c",
                {"route": "generate"},
            ),
        ]
    )

    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    target = [
        f
        for f in findings
        if f.file_path.as_posix() == "extensions/anthropic/src/api"
        and f.metadata.get("category") == PatternCategory.ERROR_HANDLING.value
    ]

    assert len(target) == 1
    finding = target[0]
    assert finding.metadata["framework_context_dampened"] is True
    assert finding.metadata["plugin_context_dampened"] is True
    assert finding.metadata["combined_plugin_framework_cap"] is True
    assert finding.severity == Severity.INFO


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


# ---------------------------------------------------------------------------
# RETURN_PATTERN detection through PFS
# ---------------------------------------------------------------------------


def test_return_pattern_two_variants_detected():
    """Two different return-strategy fingerprints in one module → PFS finding."""
    fp_none_raise = {"strategies": ["raise", "return_none"]}
    fp_tuple_value = {"strategies": ["return_tuple", "return_value"]}
    patterns = [
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "get_user", fp_none_raise),
        _make_pattern(
            PatternCategory.RETURN_PATTERN,
            "models",
            "get_user_or_raise",
            fp_tuple_value,
        ),
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    assert findings[0].signal_type == SignalType.PATTERN_FRAGMENTATION
    assert "return_pattern" in findings[0].title
    assert findings[0].metadata["num_variants"] == 2


def test_return_pattern_single_variant_no_finding():
    """All functions share the same return-strategy fingerprint → no finding."""
    fp = {"strategies": ["raise", "return_value"]}
    patterns = [
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "func_a", fp),
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "func_b", fp),
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert findings == []


def test_return_pattern_three_variants():
    """Three distinct return-strategy fingerprints → higher fragmentation score."""
    fp_a = {"strategies": ["raise", "return_value"]}
    fp_b = {"strategies": ["return_none", "return_value"]}
    fp_c = {"strategies": ["return_tuple"]}
    patterns = [
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "get_user", fp_a),
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "get_or_raise", fp_b),
        _make_pattern(PatternCategory.RETURN_PATTERN, "models", "get_result", fp_c),
    ]
    findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
    assert len(findings) == 1
    assert findings[0].metadata["num_variants"] == 3
    assert findings[0].score >= 0.5
