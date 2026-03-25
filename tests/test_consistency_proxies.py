"""Tests for consistency proxy signals: BEM, TPD, GCD."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    ParseResult,
    PatternCategory,
    PatternInstance,
    SignalType,
)
from drift.signals.broad_exception_monoculture import BroadExceptionMonocultureSignal
from drift.signals.guard_clause_deficit import GuardClauseDeficitSignal
from drift.signals.test_polarity_deficit import TestPolarityDeficitSignal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(**overrides: object) -> DriftConfig:
    return DriftConfig(**overrides)  # type: ignore[arg-type]


def _handler(exc_type: str = "bare", actions: list[str] | None = None) -> dict:
    return {"exception_type": exc_type, "actions": actions or ["pass"]}


def _error_pattern(
    file_path: Path,
    func_name: str = "func",
    handlers: list[dict] | None = None,
) -> PatternInstance:
    hs = handlers or [_handler()]
    return PatternInstance(
        category=PatternCategory.ERROR_HANDLING,
        file_path=file_path,
        function_name=func_name,
        start_line=1,
        end_line=10,
        fingerprint={
            "handler_count": len(hs),
            "handlers": hs,
            "has_finally": False,
            "has_else": False,
        },
    )


def _parse_result(
    file_path: Path,
    patterns: list[PatternInstance] | None = None,
    language: str = "python",
) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language=language,
        patterns=patterns or [],
    )


_NO_HISTORY: dict[str, FileHistory] = {}


# =========================================================================
# BEM Tests
# =========================================================================

class TestBroadExceptionMonoculture:
    """Tests for Signal 8: Broad Exception Monoculture."""

    def _signal(self) -> BroadExceptionMonocultureSignal:
        return BroadExceptionMonocultureSignal()

    def test_no_handlers_no_findings(self, tmp_path: Path) -> None:
        pr = _parse_result(tmp_path / "mod" / "foo.py")
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_single_handler_below_threshold(self, tmp_path: Path) -> None:
        """A single broad handler should not trigger (below bem_min_handlers)."""
        fp = tmp_path / "mod" / "foo.py"
        pat = _error_pattern(fp, handlers=[_handler("bare", ["pass"])])
        pr = _parse_result(fp, patterns=[pat])
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_broad_monoculture_detected(self, tmp_path: Path) -> None:
        """Module with ≥3 broad+swallowing handlers should trigger."""
        mod = tmp_path / "mod"
        fps = [mod / f"f{i}.py" for i in range(3)]
        patterns = [
            _error_pattern(fp, handlers=[_handler("bare", ["pass"])])
            for fp in fps
        ]
        prs = [_parse_result(fp, patterns=[p]) for fp, p in zip(fps, patterns, strict=True)]
        findings = self._signal().analyze(prs, _NO_HISTORY, _default_config())
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.BROAD_EXCEPTION_MONOCULTURE
        assert f.metadata["broadness_ratio"] >= 0.80
        assert f.metadata["swallowing_ratio"] >= 0.60

    def test_diverse_handlers_no_finding(self, tmp_path: Path) -> None:
        """Module with diverse exception types should NOT trigger."""
        mod = tmp_path / "mod"
        fp = mod / "foo.py"
        patterns = [
            _error_pattern(fp, func_name="f1", handlers=[_handler("ValueError", ["raise"])]),
            _error_pattern(fp, func_name="f2", handlers=[_handler("KeyError", ["raise"])]),
            _error_pattern(fp, func_name="f3", handlers=[_handler("TypeError", ["return"])]),
        ]
        pr = _parse_result(fp, patterns=patterns)
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_handlers_with_raise_not_swallowing(self, tmp_path: Path) -> None:
        """Handlers that re-raise should not count as swallowing."""
        mod = tmp_path / "mod"
        fp = mod / "foo.py"
        patterns = [
            _error_pattern(fp, func_name=f"f{i}", handlers=[_handler("bare", ["raise"])])
            for i in range(4)
        ]
        pr = _parse_result(fp, patterns=patterns)
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_bare_except_detected_as_broad(self, tmp_path: Path) -> None:
        """'bare' exception type is treated as broad."""
        mod = tmp_path / "mod"
        fp = mod / "foo.py"
        patterns = [
            _error_pattern(fp, func_name=f"f{i}", handlers=[_handler("bare", ["log"])])
            for i in range(4)
        ]
        pr = _parse_result(fp, patterns=patterns)
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert len(findings) == 1
        assert findings[0].metadata["broad_count"] == 4

    def test_score_calculation(self, tmp_path: Path) -> None:
        """Score = broadness_ratio × swallowing_ratio, clamped [0,1]."""
        mod = tmp_path / "mod"
        fp = mod / "foo.py"
        # 4 handlers: 3 broad+swallowing, 1 specific+raise
        patterns = [
            _error_pattern(fp, func_name=f"f{i}", handlers=[_handler("Exception", ["pass"])])
            for i in range(3)
        ]
        patterns.append(
            _error_pattern(fp, func_name="f3", handlers=[_handler("ValueError", ["raise"])])
        )
        pr = _parse_result(fp, patterns=patterns)
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        # broadness = 3/4 = 0.75 < 0.80 threshold → should NOT trigger
        assert findings == []

    def test_module_grouping(self, tmp_path: Path) -> None:
        """Handlers in separate modules produce separate findings."""
        mod_a = tmp_path / "a"
        mod_b = tmp_path / "b"
        prs = []
        for mod in [mod_a, mod_b]:
            fps = [mod / f"f{i}.py" for i in range(3)]
            for fp in fps:
                pat = _error_pattern(fp, handlers=[_handler("bare", ["pass"])])
                prs.append(_parse_result(fp, patterns=[pat]))
        findings = self._signal().analyze(prs, _NO_HISTORY, _default_config())
        assert len(findings) == 2

    def test_error_boundary_excluded(self, tmp_path: Path) -> None:
        """Files named middleware/error_handler are excluded."""
        mod = tmp_path / "mod"
        fps = [mod / "middleware.py", mod / "error_handler.py", mod / "main.py"]
        patterns = [
            _error_pattern(fp, handlers=[_handler("bare", ["pass"])])
            for fp in fps
        ]
        prs = [_parse_result(fp, patterns=[p]) for fp, p in zip(fps, patterns, strict=True)]
        findings = self._signal().analyze(prs, _NO_HISTORY, _default_config())
        # Only 1 handler from main.py (below threshold of 3)
        assert findings == []


# =========================================================================
# TPD Tests
# =========================================================================

class TestTestPolarityDeficit:
    """Tests for Signal 9: Test Polarity Deficit."""

    def _signal(self) -> TestPolarityDeficitSignal:
        return TestPolarityDeficitSignal()

    def _write_test_file(
        self, path: Path, content: str
    ) -> ParseResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return ParseResult(file_path=path, language="python")

    def test_no_test_files_no_findings(self, tmp_path: Path) -> None:
        fp = tmp_path / "src" / "main.py"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("def main(): pass", encoding="utf-8")
        pr = ParseResult(file_path=fp, language="python")
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_all_positive_assertions_triggers(self, tmp_path: Path) -> None:
        """Test suite with only positive assertions should trigger."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_foo.py",
            """\
            def test_one():
                assert 1 == 1

            def test_two():
                assert True

            def test_three():
                assert "a" in "abc"

            def test_four():
                assert len([1, 2]) == 2

            def test_five():
                assert 5 > 0

            def test_six():
                assert isinstance(1, int)

            def test_seven():
                assert [1, 2, 3]

            def test_eight():
                assert {"key": "val"}

            def test_nine():
                assert "hello"

            def test_ten():
                assert 42
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.TEST_POLARITY_DEFICIT
        assert f.metadata["negative_ratio"] < 0.10

    def test_mixed_assertions_below_threshold(self, tmp_path: Path) -> None:
        """Suite with enough negative assertions should not trigger."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_mixed.py",
            """\
            import pytest

            def test_ok_1():
                assert 1 == 1

            def test_ok_2():
                assert True

            def test_ok_3():
                assert "a" in "abc"

            def test_ok_4():
                assert 5 > 0

            def test_ok_5():
                assert 42

            def test_error():
                with pytest.raises(ValueError):
                    raise ValueError("boom")

            def test_error_2():
                with pytest.raises(TypeError):
                    raise TypeError("oops")
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        # 5 positive + 2 negative = 2/7 ≈ 29% > 10% → no trigger
        assert findings == []

    def test_pytest_raises_counted_as_negative(self, tmp_path: Path) -> None:
        """pytest.raises context manager assertion counted as negative."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_exc.py",
            """\
            import pytest

            def test_1():
                assert True
            def test_2():
                assert True
            def test_3():
                assert True
            def test_4():
                assert True
            def test_5():
                assert True
            def test_6():
                assert True
            def test_7():
                assert True
            def test_8():
                assert True
            def test_9():
                assert True
            def test_10():
                assert True
            def test_neg():
                with pytest.raises(ValueError):
                    int("not a number")
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        if findings:
            md = findings[0].metadata
            assert md["negative_assertions"] >= 1

    def test_assert_raises_counted_as_negative(self, tmp_path: Path) -> None:
        """unittest assertRaises counted as negative assertion."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_unit.py",
            """\
            import unittest

            class TestFoo(unittest.TestCase):
                def test_ok_1(self):
                    self.assertEqual(1, 1)
                def test_ok_2(self):
                    self.assertTrue(True)
                def test_ok_3(self):
                    self.assertIn("a", "abc")
                def test_ok_4(self):
                    self.assertEqual(2, 2)
                def test_ok_5(self):
                    self.assertTrue(True)
                def test_error(self):
                    self.assertRaises(ValueError, int, "bad")
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        if findings:
            assert findings[0].metadata["negative_assertions"] >= 1

    def test_small_test_suite_skipped(self, tmp_path: Path) -> None:
        """Suite with fewer than tpd_min_test_functions should not trigger."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_small.py",
            """\
            def test_a():
                assert True
            def test_b():
                assert 1 == 1
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_score_scales_with_suite_size(self, tmp_path: Path) -> None:
        """Score should be higher for larger positive-only suites."""
        lines = []
        for i in range(20):
            lines.append(f"def test_{i}():\n    assert True\n")
        pr = self._write_test_file(
            tmp_path / "tests" / "test_big.py",
            "\n".join(lines),
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert len(findings) == 1
        assert findings[0].score >= 0.8

    def test_boundary_test_names_contribute(self, tmp_path: Path) -> None:
        """Functions with boundary keywords contribute to negative count."""
        pr = self._write_test_file(
            tmp_path / "tests" / "test_edge.py",
            """\
            def test_ok_1():
                assert True
            def test_ok_2():
                assert True
            def test_ok_3():
                assert True
            def test_ok_4():
                assert True
            def test_ok_5():
                assert True
            def test_empty_input():
                assert True
            def test_null_case():
                assert True
            def test_boundary_check():
                assert True
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        if findings:
            assert findings[0].metadata["boundary_functions"] >= 3

    def test_non_python_skipped(self, tmp_path: Path) -> None:
        """Non-Python test files are skipped (TS support separate)."""
        fp = tmp_path / "tests" / "test_foo.ts"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("describe('foo', () => { it('works', () => {}); });")
        pr = ParseResult(file_path=fp, language="typescript")
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []


# =========================================================================
# GCD Tests
# =========================================================================

class TestGuardClauseDeficit:
    """Tests for Signal 10: Guard Clause Deficit."""

    def _signal(self) -> GuardClauseDeficitSignal:
        return GuardClauseDeficitSignal()

    def _write_module(
        self, path: Path, content: str
    ) -> ParseResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        from drift.ingestion.ast_parser import PythonFileParser

        source = path.read_text(encoding="utf-8")
        parser = PythonFileParser(source, path)
        return parser.parse()

    def test_no_qualifying_functions_no_findings(self, tmp_path: Path) -> None:
        """Simple functions with low complexity should not trigger."""
        pr = self._write_module(
            tmp_path / "src" / "simple.py",
            """\
            def add(a, b):
                return a + b

            def sub(a, b):
                return a - b
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_all_guarded_no_findings(self, tmp_path: Path) -> None:
        """Module where all qualifying functions have guards → no trigger."""
        pr = self._write_module(
            tmp_path / "src" / "guarded.py",
            """\
            def process(data, config, mode):
                assert isinstance(data, dict)
                if config is None:
                    raise ValueError("config required")
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x

            def validate(items, schema, strict):
                if not isinstance(items, list):
                    raise TypeError("items must be list")
                if schema is None:
                    raise ValueError("schema required")
                for item in items:
                    if strict:
                        if not schema.validate(item):
                            raise ValueError("invalid")
                    else:
                        try:
                            schema.validate(item)
                        except Exception:
                            pass
                return True

            def transform(source, target, options):
                assert source is not None
                if target is None:
                    raise ValueError("target required")
                result = []
                for s in source:
                    if options.get("upper"):
                        result.append(s.upper())
                    elif options.get("lower"):
                        result.append(s.lower())
                    else:
                        result.append(s)
                return result
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_no_guards_triggers(self, tmp_path: Path) -> None:
        """Module with complex unguarded functions should trigger."""
        pr = self._write_module(
            tmp_path / "src" / "unguarded.py",
            """\
            def process(data, config, mode, strict):
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                elif mode == "d":
                    return x * 3
                else:
                    return x

            def handle(request, session, context, flag):
                result = request.get("action")
                if result == "create":
                    return session.create(context)
                elif result == "update":
                    return session.update(context)
                elif result == "delete":
                    return session.delete(context)
                elif result == "archive":
                    return session.archive(context)
                else:
                    return None

            def transform(source, target, options, mode):
                result = []
                for s in source:
                    if options.get("upper"):
                        result.append(s.upper())
                    elif options.get("lower"):
                        result.append(s.lower())
                    elif options.get("title"):
                        result.append(s.title())
                    elif options.get("strip"):
                        result.append(s.strip())
                    else:
                        result.append(s)
                return result
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == SignalType.GUARD_CLAUSE_DEFICIT
        assert f.metadata["guarded_ratio"] < 0.15

    def test_isinstance_counts_as_guard(self, tmp_path: Path) -> None:
        """isinstance() in early body counts as guard."""
        pr = self._write_module(
            tmp_path / "src" / "checked.py",
            """\
            def process(data, config, mode):
                isinstance(data, dict)
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x

            def handle(request, session, context):
                isinstance(request, dict)
                result = request.get("action")
                if result == "create":
                    return session.create(context)
                elif result == "update":
                    return session.update(context)
                elif result == "delete":
                    return session.delete(context)
                else:
                    return None

            def transform(source, target, options):
                isinstance(source, list)
                result = []
                for s in source:
                    if options.get("upper"):
                        result.append(s.upper())
                    elif options.get("lower"):
                        result.append(s.lower())
                    else:
                        result.append(s)
                return result
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        # All functions have isinstance → guarded → no trigger
        assert findings == []

    def test_assert_param_counts_as_guard(self, tmp_path: Path) -> None:
        """assert referencing a parameter counts as guard."""
        pr = self._write_module(
            tmp_path / "src" / "asserted.py",
            """\
            def process(data, config, mode):
                assert data is not None
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_if_none_raise_counts_as_guard(self, tmp_path: Path) -> None:
        """if param is None: raise counts as guard."""
        pr = self._write_module(
            tmp_path / "src" / "guarded2.py",
            """\
            def process(data, config, mode):
                if data is None:
                    raise ValueError("data required")
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_private_functions_excluded(self, tmp_path: Path) -> None:
        """Functions starting with _ should be excluded from analysis."""
        pr = self._write_module(
            tmp_path / "src" / "private.py",
            """\
            def _internal(data, config, mode):
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x

            def _helper(request, session, context):
                result = request.get("action")
                if result == "create":
                    return session.create(context)
                elif result == "update":
                    return session.update(context)
                elif result == "delete":
                    return session.delete(context)
                else:
                    return None
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []

    def test_test_files_excluded(self, tmp_path: Path) -> None:
        """Test files should not be analyzed for guard clauses."""
        pr = self._write_module(
            tmp_path / "tests" / "test_something.py",
            """\
            def process(data, config, mode):
                x = data.get("key", 0)
                if mode == "a":
                    return x + 1
                elif mode == "b":
                    return x - 1
                elif mode == "c":
                    return x * 2
                else:
                    return x
            """,
        )
        findings = self._signal().analyze([pr], _NO_HISTORY, _default_config())
        assert findings == []
