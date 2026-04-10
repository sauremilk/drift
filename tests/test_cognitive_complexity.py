"""Tests for Cognitive Complexity signal (CXS)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import FunctionInfo, ParseResult, SignalType
from drift.precision import (
    ensure_signals_registered,
    has_matching_finding,
    run_fixture,
)
from drift.signals.cognitive_complexity import (
    CognitiveComplexitySignal,
    _cognitive_complexity_of_body,
)
from tests.fixtures.ground_truth import FIXTURES_BY_SIGNAL, GroundTruthFixture


def _make_pr(
    file_path: str,
    functions: list[FunctionInfo],
    *,
    language: str = "python",
) -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language=language,
        functions=functions,
    )


def _func(
    name: str,
    file_path: str,
    start: int,
    end: int,
    *,
    complexity: int = 10,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=start,
        end_line=end,
        language="python",
        complexity=complexity,
        loc=end - start + 1,
    )


# ---------------------------------------------------------------------------
# Unit tests for _cognitive_complexity_of_body
# ---------------------------------------------------------------------------


def test_flat_function_has_zero_complexity() -> None:
    import ast

    source = textwrap.dedent("""\
        def f(x):
            a = 1
            b = 2
            return a + b
    """)
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    assert _cognitive_complexity_of_body(func.body) == 0


def test_single_if_has_complexity_one() -> None:
    import ast

    source = textwrap.dedent("""\
        def f(x):
            if x > 0:
                return x
            return -x
    """)
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    cc = _cognitive_complexity_of_body(func.body)
    assert cc >= 1


def test_nested_if_gets_nesting_bonus() -> None:
    import ast

    source = textwrap.dedent("""\
        def f(x, y):
            if x > 0:
                if y > 0:
                    return x + y
            return 0
    """)
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    cc = _cognitive_complexity_of_body(func.body)
    # outer if: +1 (nesting 0), inner if: +1 + 1 nesting bonus = +2
    assert cc >= 3


def test_loop_with_nested_condition() -> None:
    import ast

    source = textwrap.dedent("""\
        def f(items):
            for item in items:
                if item.valid:
                    if item.active:
                        process(item)
    """)
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    cc = _cognitive_complexity_of_body(func.body)
    # for: +1, if: +1+1, if: +1+2 = 6
    assert cc >= 5


# ---------------------------------------------------------------------------
# Integration tests for CognitiveComplexitySignal.analyze()
# ---------------------------------------------------------------------------


class TestCXSTruePositive:
    """Complex function should trigger a finding."""

    def test_complex_function_detected(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            def process_order(order, user, config, db):
                if order.status == "pending":
                    if user.is_active:
                        for item in order.items:
                            if item.stock > 0:
                                if config.validate:
                                    if item.price > 0:
                                        try:
                                            db.save(item)
                                        except Exception:
                                            if config.retry:
                                                db.save(item)
                                            else:
                                                raise
                return None
        """)
        src_file = tmp_path / "services" / "order_service.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text(source)

        pr = ParseResult(
            file_path=Path("services/order_service.py"),
            language="python",
            functions=[
                FunctionInfo(
                    name="process_order",
                    file_path=Path("services/order_service.py"),
                    start_line=1,
                    end_line=16,
                    language="python",
                    complexity=10,
                    loc=16,
                ),
            ],
        )

        signal = CognitiveComplexitySignal()
        signal._repo_path = tmp_path
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) >= 1
        f = findings[0]
        assert f.signal_type == SignalType.COGNITIVE_COMPLEXITY
        assert f.metadata["cognitive_complexity"] > 15
        assert f.score > 0.3


class TestCXSTrueNegative:
    """Simple function should not trigger a finding."""

    def test_simple_function_not_detected(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            def add(a, b):
                return a + b

            def multiply(a, b):
                return a * b

            def greet(name):
                if not name:
                    return "Hello"
                return f"Hello {name}"
        """)
        src_file = tmp_path / "utils" / "math.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text(source)

        pr = ParseResult(
            file_path=Path("utils/math.py"),
            language="python",
            functions=[
                FunctionInfo(
                    name="add",
                    file_path=Path("utils/math.py"),
                    start_line=1,
                    end_line=2,
                    language="python",
                    complexity=1,
                    loc=2,
                ),
                FunctionInfo(
                    name="multiply",
                    file_path=Path("utils/math.py"),
                    start_line=4,
                    end_line=5,
                    language="python",
                    complexity=1,
                    loc=2,
                ),
                FunctionInfo(
                    name="greet",
                    file_path=Path("utils/math.py"),
                    start_line=7,
                    end_line=10,
                    language="python",
                    complexity=2,
                    loc=4,
                ),
            ],
        )

        signal = CognitiveComplexitySignal()
        signal._repo_path = tmp_path
        findings = signal.analyze([pr], {}, DriftConfig())

        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Parametrized ground-truth fixture tests
# ---------------------------------------------------------------------------

ensure_signals_registered()

_CXS_FIXTURES = FIXTURES_BY_SIGNAL.get(SignalType.COGNITIVE_COMPLEXITY, [])


@pytest.mark.parametrize(
    "fixture",
    _CXS_FIXTURES,
    ids=[f.name for f in _CXS_FIXTURES],
)
def test_cxs_ground_truth(fixture: GroundTruthFixture, tmp_path: Path) -> None:
    """Verify CXS ground-truth fixtures produce expected findings."""
    findings, _warnings = run_fixture(
        fixture, tmp_path, signal_filter={SignalType.COGNITIVE_COMPLEXITY}
    )
    for exp in fixture.expected:
        if exp.signal_type != SignalType.COGNITIVE_COMPLEXITY:
            continue
        detected = has_matching_finding(findings, exp)
        if exp.should_detect:
            assert detected, (
                f"[FN] {fixture.name}: expected CXS at {exp.file_path} "
                f"but not found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
        else:
            assert not detected, (
                f"[FP] {fixture.name}: did NOT expect CXS at {exp.file_path} "
                f"but found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
