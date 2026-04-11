"""Tests for Phase 3 TypeScript signal support (ECM, TPD).

Verifies that ExceptionContractDrift and TestPolarityDeficit correctly
process TypeScript/JavaScript source code via tree-sitter.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    FunctionInfo,
    ParseResult,
    SignalType,
)
from drift.signals.exception_contract_drift import (
    ExceptionContractDriftSignal,
    _ts_extract_functions_from_source,
)
from drift.signals.test_polarity_deficit import (
    TestPolarityDeficitSignal,
    _ts_count_assertions,
)

ts_available: bool
try:
    import tree_sitter  # noqa: F401
    import tree_sitter_typescript  # noqa: F401

    ts_available = True
except ImportError:
    ts_available = False

needs_tree_sitter = pytest.mark.skipif(
    not ts_available, reason="tree-sitter-typescript not installed"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**overrides: object) -> DriftConfig:
    thresholds = {}
    for k, v in overrides.items():
        thresholds[k] = v
    return DriftConfig(thresholds=thresholds) if thresholds else DriftConfig()


def _ts_pr(
    file_path: Path,
    *,
    language: str = "typescript",
    functions: list[FunctionInfo] | None = None,
) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language=language,
        functions=functions or [],
        imports=[],
        patterns=[],
    )


# ===================================================================
# ECM — _ts_extract_exception_profile  (unit tests)
# ===================================================================


@needs_tree_sitter
class TestTsExceptionProfile:
    """Unit tests for _ts_extract_exception_profile."""

    def _parse_func(self, code: str) -> dict:
        """Helper: extract profile from first public function."""
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert funcs, f"No functions found in:\n{code}"
        first = next(iter(funcs.values()))
        return first["profile"]

    def test_throw_new_error(self) -> None:
        code = "export function doWork(x: number) {\n  throw new ValidationError('bad');\n}"
        profile = self._parse_func(code)
        assert "ValidationError" in profile["raise_types"]

    def test_multiple_throw_types(self) -> None:
        code = """
export function process(data: string) {
  if (!data) throw new TypeError('empty');
  try { JSON.parse(data); }
  catch (e: unknown) { throw new ParseError('invalid'); }
}
"""
        profile = self._parse_func(code)
        assert "TypeError" in profile["raise_types"]
        assert "ParseError" in profile["raise_types"]

    def test_catch_typed(self) -> None:
        code = """
export function read(path: string) {
  try { readFile(path); }
  catch (e: TypeError) { console.error(e); }
}
"""
        profile = self._parse_func(code)
        assert "TypeError" in profile["handler_types"]
        assert not profile["has_bare_except"]

    def test_catch_untyped_is_bare(self) -> None:
        code = """
export function read(path: string) {
  try { readFile(path); } catch (e) { console.error(e); }
}
"""
        profile = self._parse_func(code)
        assert profile["has_bare_except"]

    def test_no_catch_no_throw(self) -> None:
        code = "export function add(a: number, b: number) { return a + b; }"
        profile = self._parse_func(code)
        assert profile["raise_types"] == []
        assert profile["handler_types"] == []
        assert not profile["has_bare_except"]
        assert not profile["has_bare_raise"]

    def test_arrow_function_throw(self) -> None:
        code = "export const validate = (x: string) => { throw new RangeError('out'); };"
        profile = self._parse_func(code)
        assert "RangeError" in profile["raise_types"]

    def test_private_function_skipped(self) -> None:
        code = "function _helper() { throw new Error('bug'); }"
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert "_helper" not in funcs


@needs_tree_sitter
class TestTsExtractFunctions:
    """Unit tests for _ts_extract_functions_from_source."""

    def test_function_declaration(self) -> None:
        code = "export function process(a: number, b: string) { return a; }"
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert "process" in funcs
        assert funcs["process"]["param_count"] == 2

    def test_arrow_function(self) -> None:
        code = "export const handle = (req: Request, res: Response) => { res.send(); };"
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert "handle" in funcs
        assert funcs["handle"]["param_count"] == 2

    def test_method_definition(self) -> None:
        code = """
class Service {
  process(data: string, options: Config) { return data; }
}
"""
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert "process" in funcs
        assert funcs["process"]["param_count"] == 2

    def test_no_public_functions(self) -> None:
        code = "function _internal(x: number) { return x * 2; }"
        funcs = _ts_extract_functions_from_source(code, "typescript")
        assert len(funcs) == 0


# ===================================================================
# ECM — full signal integration test (mocked git)
# ===================================================================


@needs_tree_sitter
class TestEcmSignalTs:
    """Integration test for ExceptionContractDriftSignal with TS files."""

    def test_detects_exception_contract_change(self, tmp_path: Path) -> None:
        """Exception profile changed but signature stayed → finding."""
        # Current source: throws ValidationError
        current = """
export function validate(data: string) {
  if (!data) throw new ValidationError('missing');
  return JSON.parse(data);
}
"""
        # Old source: threw TypeError
        old = """
export function validate(data: string) {
  if (!data) throw new TypeError('invalid');
  return JSON.parse(data);
}
"""
        ts_file = tmp_path / "lib" / "validator.ts"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text(current, encoding="utf-8")

        pr = _ts_pr(Path("lib/validator.ts"), language="typescript")
        hist = FileHistory(
            path=Path("lib/validator.ts"),
            total_commits=5,
            last_modified="2026-01-01",
        )

        signal = ExceptionContractDriftSignal(repo_path=tmp_path)

        with patch(
            "drift.signals.exception_contract_drift._git_show_file",
            return_value=old,
        ):
            findings = signal.analyze(
                [pr],
                {"lib/validator.ts": hist},
                _cfg(),
            )

        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.EXCEPTION_CONTRACT_DRIFT
        assert "validate" in findings[0].description

    def test_no_finding_when_same_profile(self, tmp_path: Path) -> None:
        """Unchanged exception profile → no finding."""
        source = """
export function validate(data: string) {
  if (!data) throw new TypeError('bad');
}
"""
        ts_file = tmp_path / "lib" / "validator.ts"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text(source, encoding="utf-8")

        pr = _ts_pr(Path("lib/validator.ts"))
        hist = FileHistory(
            path=Path("lib/validator.ts"),
            total_commits=5,
            last_modified="2026-01-01",
        )

        signal = ExceptionContractDriftSignal(repo_path=tmp_path)

        with patch(
            "drift.signals.exception_contract_drift._git_show_file",
            return_value=source,
        ):
            findings = signal.analyze(
                [pr],
                {"lib/validator.ts": hist},
                _cfg(),
            )

        assert len(findings) == 0

    def test_no_finding_when_signature_changed(self, tmp_path: Path) -> None:
        """If param count changes, it's an intentional refactor → no finding."""
        current = """
export function validate(data: string, strict: boolean) {
  if (!data) throw new ValidationError('bad');
}
"""
        old = """
export function validate(data: string) {
  if (!data) throw new TypeError('bad');
}
"""
        ts_file = tmp_path / "lib" / "validator.ts"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text(current, encoding="utf-8")

        pr = _ts_pr(Path("lib/validator.ts"))
        hist = FileHistory(
            path=Path("lib/validator.ts"),
            total_commits=5,
            last_modified="2026-01-01",
        )

        signal = ExceptionContractDriftSignal(repo_path=tmp_path)

        with patch(
            "drift.signals.exception_contract_drift._git_show_file",
            return_value=old,
        ):
            findings = signal.analyze(
                [pr],
                {"lib/validator.ts": hist},
                _cfg(),
            )

        assert len(findings) == 0


# ===================================================================
# TPD — _ts_count_assertions  (unit tests)
# ===================================================================


@needs_tree_sitter
class TestTsAssertionCounter:
    """Unit tests for _ts_count_assertions."""

    def test_positive_assertions(self) -> None:
        code = """
import { describe, it, expect } from 'vitest';
describe('math', () => {
  it('adds numbers', () => {
    expect(1 + 1).toBe(2);
    expect([1, 2]).toContain(1);
    expect('hello').toEqual('hello');
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert pos >= 3
        assert neg == 0
        assert tfuncs == 1

    def test_negative_assertions(self) -> None:
        code = """
import { describe, it, expect } from 'vitest';
describe('validation', () => {
  it('throws on empty', () => {
    expect(() => validate('')).toThrow();
    expect(() => validate(null)).toThrowError('invalid');
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert neg >= 2
        assert pos == 0

    def test_mixed_assertions(self) -> None:
        code = """
describe('user service', () => {
  it('creates user', () => {
    expect(createUser('test')).toBeDefined();
    expect(createUser('test').name).toBe('test');
  });
  it('rejects invalid email', () => {
    expect(() => createUser('')).toThrow();
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert pos >= 2
        assert neg >= 1
        assert tfuncs == 2

    def test_boundary_keyword_detection(self) -> None:
        code = """
describe('validator', () => {
  it('handles empty input', () => {
    expect(validate('')).toBeFalsy();
  });
  it('handles null value', () => {
    expect(validate(null)).toBeNull();
  });
  it('normal case', () => {
    expect(validate('ok')).toBe(true);
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert bfuncs >= 2  # "empty" and "null" are boundary keywords
        assert tfuncs == 3

    def test_assert_throws_node_style(self) -> None:
        code = """
describe('parser', () => {
  it('rejects bad json', () => {
    assert.throws(() => parse('{}bad'));
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert neg >= 1

    def test_not_matcher_counted_as_negative(self) -> None:
        code = """
describe('feature', () => {
  it('is not enabled by default', () => {
    expect(isEnabled()).not.toBe(true);
  });
});
"""
        result = _ts_count_assertions(code, "typescript")
        assert result is not None
        pos, neg, tfuncs, bfuncs = result
        assert neg >= 1


# ===================================================================
# TPD — full signal integration test
# ===================================================================


@needs_tree_sitter
class TestTpdSignalTs:
    """Integration test for TestPolarityDeficitSignal with TS test files."""

    def test_detects_happy_path_only_suite(self, tmp_path: Path) -> None:
        """TS test file with only positive assertions → finding."""
        # Generate enough test functions and assertions to exceed thresholds
        tests = []
        for i in range(8):
            tests.append(f"""
  it('test case {i}', () => {{
    expect(process({i})).toBe({i});
    expect(process({i})).toEqual({i});
  }});""")

        code = f"""
import {{ describe, it, expect }} from 'vitest';
describe('processor', () => {{
{"".join(tests)}
}});
"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "processor.test.ts"
        test_file.write_text(code, encoding="utf-8")

        pr = _ts_pr(Path("tests/processor.test.ts"), language="typescript")

        signal = TestPolarityDeficitSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, _cfg(tpd_min_test_functions=5))

        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.TEST_POLARITY_DEFICIT
        meta = findings[0].metadata
        assert meta["test_functions"] >= 8
        assert meta["positive_assertions"] >= 16
        assert meta["negative_assertions"] == 0

    def test_no_finding_with_enough_negative_tests(self, tmp_path: Path) -> None:
        """TS test file with sufficient negative assertions → no finding."""
        tests = []
        # 5 positive tests
        for i in range(5):
            tests.append(f"""
  it('works for case {i}', () => {{
    expect(compute({i})).toBe({i});
  }});""")
        # 3 negative tests (≥10% ratio)
        for i in range(3):
            tests.append(f"""
  it('throws on bad input {i}', () => {{
    expect(() => compute(-{i})).toThrow();
  }});""")

        code = f"""
import {{ describe, it, expect }} from 'vitest';
describe('compute', () => {{
{"".join(tests)}
}});
"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "compute.test.ts"
        test_file.write_text(code, encoding="utf-8")

        pr = _ts_pr(Path("tests/compute.test.ts"), language="typescript")

        signal = TestPolarityDeficitSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, _cfg(tpd_min_test_functions=5))

        assert len(findings) == 0

    def test_skips_non_test_file(self, tmp_path: Path) -> None:
        """Non-test TS file should be skipped."""
        code = """
export function compute(x: number) { return x * 2; }
"""
        lib_dir = tmp_path / "src"
        lib_dir.mkdir()
        src_file = lib_dir / "compute.ts"
        src_file.write_text(code, encoding="utf-8")

        pr = _ts_pr(Path("src/compute.ts"), language="typescript")

        signal = TestPolarityDeficitSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, _cfg(tpd_min_test_functions=1))

        assert len(findings) == 0

    def test_below_min_test_functions_threshold(self, tmp_path: Path) -> None:
        """Below tpd_min_test_functions → no finding."""
        code = """
describe('small suite', () => {
  it('works', () => {
    expect(1).toBe(1);
  });
});
"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "small.test.ts"
        test_file.write_text(code, encoding="utf-8")

        pr = _ts_pr(Path("tests/small.test.ts"), language="typescript")

        signal = TestPolarityDeficitSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, _cfg(tpd_min_test_functions=5))

        assert len(findings) == 0

    def test_javascript_test_file(self, tmp_path: Path) -> None:
        """JS test files should also be analyzed."""
        tests = []
        for i in range(6):
            tests.append(f"""
  it('test case {i}', () => {{
    expect(doWork({i})).toBe({i});
    expect(doWork({i})).toEqual({i});
  }});""")

        code = f"""
describe('worker', () => {{
{"".join(tests)}
}});
"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "worker.test.js"
        test_file.write_text(code, encoding="utf-8")

        pr = _ts_pr(
            Path("tests/worker.test.js"),
            language="javascript",
        )

        signal = TestPolarityDeficitSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, _cfg(tpd_min_test_functions=5))

        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.TEST_POLARITY_DEFICIT
