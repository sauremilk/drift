"""Tests for the three consistency-proxy signals (ADR-007).

BEM — Broad Exception Monoculture
TPD — Test Polarity Deficit
GCD — Guard Clause Deficit
"""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.ast_parser import PythonFileParser
from drift.models import (
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


def _cfg(**overrides: object) -> DriftConfig:
    """Return a default DriftConfig with optional threshold overrides."""
    thresholds = {}
    for k, v in overrides.items():
        thresholds[k] = v
    if thresholds:
        return DriftConfig(thresholds=thresholds)
    return DriftConfig()


def _handler(exc_type: str = "Exception", actions: list[str] | None = None) -> dict:
    """Build a handler fingerprint dict."""
    return {
        "exception_type": exc_type,
        "actions": actions if actions is not None else ["pass"],
    }


def _pattern(file_path: Path, handlers: list[dict]) -> PatternInstance:
    """Build a PatternInstance with error-handling fingerprint."""
    return PatternInstance(
        category=PatternCategory.ERROR_HANDLING,
        file_path=file_path,
        function_name="handler",
        start_line=1,
        end_line=10,
        fingerprint={"handlers": handlers},
    )


def _parse_result(
    file_path: Path,
    patterns: list[PatternInstance] | None = None,
    functions: list | None = None,
    language: str = "python",
) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language=language,
        patterns=patterns or [],
        functions=functions or [],
        classes=[],
        imports=[],
    )


def _write_module(tmp_path: Path, rel: str, source: str) -> ParseResult:
    """Write a Python source file, parse it, and return the ParseResult."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    parser = PythonFileParser(source, p)
    return parser.parse()


# ===================================================================
# BEM — Broad Exception Monoculture
# ===================================================================


class TestBEM:
    """Tests for BroadExceptionMonocultureSignal."""

    def _run(self, parse_results: list[ParseResult], **kw: object):
        sig = BroadExceptionMonocultureSignal()
        return sig.analyze(parse_results, {}, _cfg(**kw))

    # -- no findings ---------------------------------------------------

    def test_no_handlers_no_findings(self):
        pr = _parse_result(Path("src/mod/a.py"))
        assert self._run([pr]) == []

    def test_single_handler_below_threshold(self):
        pr = _parse_result(
            Path("src/mod/a.py"),
            patterns=[_pattern(Path("src/mod/a.py"), [_handler()])],
        )
        assert self._run([pr]) == []

    # -- triggers ------------------------------------------------------

    def test_broad_monoculture_detected(self):
        fp = Path("src/mod/a.py")
        handlers = [_handler("Exception", ["pass"])] * 4
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.BROAD_EXCEPTION_MONOCULTURE

    def test_diverse_handlers_no_finding(self):
        fp = Path("src/mod/a.py")
        handlers = [
            _handler("ValueError", ["raise"]),
            _handler("TypeError", ["raise"]),
            _handler("OSError", ["log"]),
            _handler("KeyError", ["return"]),
        ]
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        assert self._run([pr]) == []

    def test_handlers_with_raise_not_swallowing(self):
        fp = Path("src/mod/a.py")
        handlers = [_handler("Exception", ["raise"])] * 4
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        assert self._run([pr]) == []

    def test_bare_except_detected_as_broad(self):
        fp = Path("src/mod/a.py")
        handlers = [_handler("bare", ["pass"])] * 4
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_fallback_assignment_counts_as_swallowing(self):
        fp = Path("src/mod/a.py")
        handlers = [_handler("Exception", ["fallback_assign"])] * 4
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_score_calculation(self):
        fp = Path("src/mod/a.py")
        # 4/5 broad (0.8), 4/5 swallowing (0.8) → score = 0.64
        handlers = [
            _handler("Exception", ["pass"]),
            _handler("Exception", ["pass"]),
            _handler("Exception", ["pass"]),
            _handler("Exception", ["pass"]),
            _handler("ValueError", ["raise"]),
        ]
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1
        assert findings[0].score == round(0.8 * 0.8, 3)

    def test_module_grouping(self):
        fp_a = Path("src/mod_a/x.py")
        fp_b = Path("src/mod_b/y.py")
        handlers = [_handler("Exception", ["pass"])] * 4
        pr_a = _parse_result(fp_a, patterns=[_pattern(fp_a, handlers)])
        pr_b = _parse_result(fp_b, patterns=[_pattern(fp_b, handlers)])
        findings = self._run([pr_a, pr_b])
        assert len(findings) == 2
        modules = {f.file_path.as_posix() for f in findings}
        assert "src/mod_a" in modules
        assert "src/mod_b" in modules

    def test_error_boundary_excluded(self):
        fp = Path("src/mod/error_handler.py")
        handlers = [_handler("Exception", ["pass"])] * 4
        pr = _parse_result(fp, patterns=[_pattern(fp, handlers)])
        assert self._run([pr]) == []


# ===================================================================
# TPD — Test Polarity Deficit
# ===================================================================


class TestTPD:
    """Tests for TestPolarityDeficitSignal."""

    def _run(self, parse_results: list[ParseResult], **kw: object):
        sig = TestPolarityDeficitSignal()
        return sig.analyze(parse_results, {}, _cfg(**kw))

    def test_no_test_files_no_findings(self):
        pr = _parse_result(Path("src/mod/service.py"))
        assert self._run([pr]) == []

    def test_all_positive_assertions_triggers(self, tmp_path: Path):
        source = "import unittest\nclass TestFoo(unittest.TestCase):\n" + "".join(
            f"    def test_{i}(self):\n"
            f"        self.assertEqual({i}, {i})\n"
            f"        self.assertTrue(True)\n"
            for i in range(8)
        )
        pr = _write_module(tmp_path, "tests/test_foo.py", source)
        findings = self._run([pr])
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.TEST_POLARITY_DEFICIT

    def test_mixed_assertions_below_threshold(self, tmp_path: Path):
        source = (
            "import unittest\n"
            "class TestFoo(unittest.TestCase):\n"
            + "".join(
                f"    def test_pos_{i}(self):\n"
                f"        self.assertEqual({i}, {i})\n"
                f"        self.assertTrue(True)\n"
                for i in range(6)
            )
            + "    def test_neg_1(self):\n"
            "        self.assertRaises(ValueError, int, 'x')\n"
            "        self.assertRaises(TypeError, int, None)\n"
            "    def test_neg_2(self):\n"
            "        self.assertFalse(False)\n"
        )
        pr = _write_module(tmp_path, "tests/test_bar.py", source)
        findings = self._run([pr])
        # negative_ratio = 3/15 = 0.2 → above 0.10 → no finding
        assert findings == []

    def test_pytest_raises_counted_as_negative(self, tmp_path: Path):
        source = (
            "import pytest\n"
            + "".join(
                f"def test_pos_{i}():\n    assert {i} == {i}\n    assert True\n" for i in range(5)
            )
            + "def test_neg():\n"
            "    with pytest.raises(ValueError):\n"
            "        int('x')\n"
            "def test_neg2():\n"
            "    with pytest.raises(TypeError):\n"
            "        int(None)\n"
        )
        pr = _write_module(tmp_path, "tests/test_raises.py", source)
        findings = self._run([pr])
        # 10 positive + 2 negative = 12 total, ratio = 2/12 ≈ 0.17 → no trigger
        assert findings == []

    def test_assert_raises_counted_as_negative(self, tmp_path: Path):
        source = (
            "import unittest\n"
            "class TestX(unittest.TestCase):\n"
            + "".join(
                f"    def test_{i}(self):\n"
                f"        self.assertEqual({i}, {i})\n"
                f"        self.assertTrue(True)\n"
                for i in range(6)
            )
            + "    def test_raises(self):\n"
            "        self.assertRaises(ValueError, int, 'x')\n"
        )
        pr = _write_module(tmp_path, "tests/test_raisesmethod.py", source)
        findings = self._run([pr])
        # 12 positive, 1 negative → ratio = 1/13 = 0.077 → trigger
        assert len(findings) == 1

    def test_small_test_suite_skipped(self, tmp_path: Path):
        source = "def test_one():\n    assert True\ndef test_two():\n    assert True\n"
        pr = _write_module(tmp_path, "tests/test_small.py", source)
        assert self._run([pr]) == []

    def test_score_scales_with_suite_size(self, tmp_path: Path):
        source = "import unittest\nclass TestBig(unittest.TestCase):\n" + "".join(
            f"    def test_{i}(self):\n"
            f"        self.assertEqual({i}, {i})\n"
            f"        self.assertTrue(True)\n"
            for i in range(12)
        )
        pr = _write_module(tmp_path, "tests/test_big.py", source)
        findings = self._run([pr])
        assert len(findings) == 1
        # 12 functions, 0 negative → score = 1.0 * 1.0 = 1.0
        assert findings[0].score == 1.0

    def test_boundary_names_counted(self, tmp_path: Path):
        source = (
            "import unittest\n"
            "class TestEdge(unittest.TestCase):\n"
            + "".join(
                f"    def test_pos_{i}(self):\n"
                f"        self.assertEqual({i}, {i})\n"
                f"        self.assertTrue(True)\n"
                for i in range(5)
            )
            + "    def test_empty_input(self):\n"
            "        self.assertTrue(True)\n"
            "    def test_null_case(self):\n"
            "        self.assertTrue(True)\n"
        )
        pr = _write_module(tmp_path, "tests/test_edge.py", source)
        findings = self._run([pr])
        assert len(findings) == 1
        assert findings[0].metadata["boundary_functions"] == 2

    def test_non_python_skipped(self):
        pr = _parse_result(Path("tests/test_foo.spec.ts"), language="typescript")
        # TS test files are identified but can't be AST-parsed → no crash
        assert self._run([pr]) == []


# ===================================================================
# GCD — Guard Clause Deficit
# ===================================================================


class TestGCD:
    """Tests for GuardClauseDeficitSignal."""

    def _run(self, parse_results: list[ParseResult], **kw: object):
        sig = GuardClauseDeficitSignal()
        return sig.analyze(parse_results, {}, _cfg(**kw))

    def test_no_qualifying_functions_no_findings(self, tmp_path: Path):
        source = "def simple(x):\n    return x + 1\n"
        pr = _write_module(tmp_path, "src/mod/simple.py", source)
        assert self._run([pr]) == []

    def test_all_guarded_no_findings(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def process_{i}(data, config, mode):\n"
                f"    if data is None:\n"
                f"        raise ValueError('no data')\n"
                f"    x = data\n"
                f"    if mode == 'a':\n"
                f"        x = x + 1\n"
                f"    elif mode == 'b':\n"
                f"        x = x + 2\n"
                f"    elif mode == 'c':\n"
                f"        x = x + 3\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/guarded.py", funcs)
        findings = self._run([pr])
        assert findings == []

    def test_no_guards_triggers(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def handle_{i}(data, config, mode):\n"
                f"    x = data\n"
                f"    if mode == 'a':\n"
                f"        x = x + 1\n"
                f"    elif mode == 'b':\n"
                f"        x = x + 2\n"
                f"    elif mode == 'c':\n"
                f"        x = x + 3\n"
                f"    elif mode == 'd':\n"
                f"        x = x + 4\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/unguarded.py", funcs)
        findings = self._run([pr])
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.GUARD_CLAUSE_DEFICIT

    def test_isinstance_counts_as_guard(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def validate_{i}(data, schema, strict):\n"
                f"    isinstance(data, dict)\n"
                f"    x = data\n"
                f"    if strict:\n"
                f"        x = dict(x)\n"
                f"    elif schema:\n"
                f"        x = schema\n"
                f"    elif not strict:\n"
                f"        x = {{}}\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/typed.py", funcs)
        findings = self._run([pr])
        assert findings == []

    def test_assert_param_counts_as_guard(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def check_{i}(data, config, mode):\n"
                f"    assert data is not None\n"
                f"    x = data\n"
                f"    if mode == 'a':\n"
                f"        x = x + 1\n"
                f"    elif mode == 'b':\n"
                f"        x = x + 2\n"
                f"    elif mode == 'c':\n"
                f"        x = x + 3\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/asserted.py", funcs)
        findings = self._run([pr])
        assert findings == []

    def test_if_none_raise_counts_as_guard(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def fetch_{i}(data, conn, timeout):\n"
                f"    if data is None:\n"
                f"        raise ValueError('missing')\n"
                f"    x = data\n"
                f"    if timeout > 0:\n"
                f"        x = x + timeout\n"
                f"    elif conn:\n"
                f"        x = x + 1\n"
                f"    elif not timeout:\n"
                f"        x = 0\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/guarded2.py", funcs)
        findings = self._run([pr])
        assert findings == []

    def test_private_functions_excluded(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def _internal_{i}(data, config, mode):\n"
                f"    x = data\n"
                f"    if mode == 'a':\n"
                f"        x = x + 1\n"
                f"    elif mode == 'b':\n"
                f"        x = x + 2\n"
                f"    elif mode == 'c':\n"
                f"        x = x + 3\n"
                f"    elif mode == 'd':\n"
                f"        x = x + 4\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "src/mod/private.py", funcs)
        assert self._run([pr]) == []

    def test_test_files_excluded(self, tmp_path: Path):
        funcs = ""
        for i in range(4):
            funcs += (
                f"def handle_{i}(data, config, mode):\n"
                f"    x = data\n"
                f"    if mode == 'a':\n"
                f"        x = x + 1\n"
                f"    elif mode == 'b':\n"
                f"        x = x + 2\n"
                f"    elif mode == 'c':\n"
                f"        x = x + 3\n"
                f"    elif mode == 'd':\n"
                f"        x = x + 4\n"
                f"    return x\n\n"
            )
        pr = _write_module(tmp_path, "test_something.py", funcs)
        assert self._run([pr]) == []
