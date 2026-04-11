"""Tests for Test Polarity Deficit signal (TPD)."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import ParseResult, SignalType
from drift.signals.test_polarity_deficit import (
    TestPolarityDeficitSignal,
    _AssertionCounter,
)


def test_tpd_zero_assertion_density(tmp_path: Path) -> None:
    source = textwrap.dedent("""\
        def test_a():
            x = 1
            y = 2

        def test_b():
            value = "x"

        def test_c():
            assert 1 == 1

        def test_d():
            foo = {"a": 1}

        def test_e():
            assert True

        def test_f():
            z = [1, 2, 3]
    """)
    f = tmp_path / "tests" / "test_sample.py"
    f.parent.mkdir(parents=True)
    f.write_text(source)

    pr = ParseResult(
        file_path=Path("tests/test_sample.py"),
        language="python",
    )

    signal = TestPolarityDeficitSignal()
    signal._repo_path = tmp_path

    findings = signal.analyze([pr], {}, DriftConfig())

    assert any(
        f.rule_id == "assertion_density_deficit"
        and f.signal_type == SignalType.TEST_POLARITY_DEFICIT
        for f in findings
    )


def test_tpd_counts_negative_assert_forms(tmp_path: Path) -> None:
    """Issue #143: AST-style negative asserts must count as negative polarity."""
    source = textwrap.dedent("""\
        def test_negative_not_guard():
            assert not is_valid_input("x")
            assert not has_access()

        def test_negative_false_literal():
            assert check_limit() is False
            assert check_rate() == False

        def test_negative_none_literal():
            assert maybe_value() is None
            assert maybe_reason() == None

        def test_positive_a():
            assert compute_total() > 0
            assert status() == "ok"

        def test_positive_b():
            assert is_ready() is True
            assert len(items()) >= 1

        def test_positive_c():
            assert version() == "1.0"
            assert get_name()
    """)
    f = tmp_path / "tests" / "test_polarity_forms.py"
    f.parent.mkdir(parents=True)
    f.write_text(source)

    pr = ParseResult(file_path=Path("tests/test_polarity_forms.py"), language="python")
    signal = TestPolarityDeficitSignal()
    signal._repo_path = tmp_path

    findings = signal.analyze([pr], {}, DriftConfig())

    assert not any(f.rule_id == "test_polarity_deficit" for f in findings)


def test_tpd_counts_pytest_fail_and_raises_calls() -> None:
    """Issue #143: functional raises/fail patterns should be counted as negative."""
    source = textwrap.dedent("""\
        import pytest

        def test_negative_fail():
            pytest.fail("expected failure path")

        def test_negative_raises_functional():
            pytest.raises(ValueError, parse_value, "bad")

        def test_positive():
            assert True
    """)
    counter = _AssertionCounter(source)
    counter.visit(ast.parse(source))

    assert counter.negative == 2
    assert counter.positive == 1


def test_tpd_ignores_out_of_range_assert_position_metadata() -> None:
    """Issue #180: malformed AST line metadata must not crash TPD counting."""
    source = textwrap.dedent("""\
        def test_position_guard():
            assert value == False
    """)
    tree = ast.parse(source)
    assert_node = next(node for node in ast.walk(tree) if isinstance(node, ast.Assert))
    assert_node.lineno = 10_000
    assert_node.end_lineno = 10_000

    counter = _AssertionCounter(source)
    counter.visit_Assert(assert_node)

    assert counter.negative == 1
    assert counter.positive == 0


def test_tpd_ignores_unexpected_source_segment_exception(tmp_path: Path, monkeypatch) -> None:
    """Issue #184: unexpected source-segment errors must not abort TPD analysis."""
    source = textwrap.dedent("""\
        def test_ok_1():
            assert service_ready()
            assert compute_value() == 1

        def test_ok_2():
            assert check_state()
            assert status() == "ok"

        def test_ok_3():
            assert feature_flag()
            assert payload_count() > 0

        def test_ok_4():
            assert validator_enabled()
            assert threshold() >= 0

        def test_ok_5():
            assert ping()
            assert owner() is not None
    """)
    f = tmp_path / "tests" / "test_runtime_guard.py"
    f.parent.mkdir(parents=True)
    f.write_text(source, encoding="utf-8")

    pr = ParseResult(file_path=Path("tests/test_runtime_guard.py"), language="python")
    signal = TestPolarityDeficitSignal()
    signal._repo_path = tmp_path

    def _raise_runtime_error(_source: str, _node: ast.AST) -> str:
        raise RuntimeError("synthetic source-segment failure")

    monkeypatch.setattr(
        "drift.signals.test_polarity_deficit.ast.get_source_segment",
        _raise_runtime_error,
    )

    findings = signal.analyze([pr], {}, DriftConfig())

    assert any(
        f.signal_type == SignalType.TEST_POLARITY_DEFICIT and "Happy-path-only" in f.title
        for f in findings
    )


def test_tpd_fallback_discovers_tests_when_parse_results_are_empty(tmp_path: Path) -> None:
    source = textwrap.dedent("""\
        def test_a():
            assert True
            assert 1 == 1

        def test_b():
            assert True
            assert 2 == 2

        def test_c():
            assert True
            assert 3 == 3

        def test_d():
            assert True
            assert 4 == 4

        def test_e():
            assert True
            assert 5 == 5
    """)
    f = tmp_path / "tests" / "test_only_positive.py"
    f.parent.mkdir(parents=True)
    f.write_text(source, encoding="utf-8")

    signal = TestPolarityDeficitSignal()
    signal._repo_path = tmp_path

    findings = signal.analyze([], {}, DriftConfig())

    assert any(
        f.signal_type == SignalType.TEST_POLARITY_DEFICIT and "Happy-path-only" in f.title
        for f in findings
    )
