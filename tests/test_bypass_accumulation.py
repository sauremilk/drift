"""Tests for BypassAccumulationSignal (BAT) — ADR-008."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ParseResult, SignalType
from drift.signals.bypass_accumulation import BypassAccumulationSignal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**overrides: object) -> DriftConfig:
    thresholds = {}
    for k, v in overrides.items():
        thresholds[k] = v
    if thresholds:
        return DriftConfig(thresholds=thresholds)
    return DriftConfig()


def _write_file(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_pr(file_path: Path) -> ParseResult:
    """Minimal ParseResult for a python file (no functions needed for BAT)."""
    return ParseResult(
        file_path=file_path,
        language="python",
        functions=[],
        classes=[],
        imports=[],
    )


def _run(
    parse_results: list[ParseResult],
    repo_path: Path | None = None,
    **kw: object,
):
    sig = BypassAccumulationSignal(repo_path=repo_path)
    return sig.analyze(parse_results, {}, _cfg(**kw))


def _lines(n: int, template: str = "x = {i}") -> str:
    """Generate n lines of filler code."""
    return "\n".join(template.format(i=i) for i in range(n))


# ===================================================================
# Basic marker detection
# ===================================================================


class TestMarkerDetection:
    def test_type_ignore_detected(self, tmp_path: Path):
        code = _lines(50) + "\nresult = foo()  # type: ignore\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1

    def test_noqa_detected(self, tmp_path: Path):
        code = _lines(50) + "\nimport os  # noqa: F401\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["lint"] >= 1

    def test_pragma_no_cover_detected(self, tmp_path: Path):
        code = _lines(50) + "\nif DEBUG:  # pragma: no cover\n    pass\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["coverage"] >= 1

    def test_cast_detected(self, tmp_path: Path):
        code = _lines(50) + "\ny = cast(int, x)\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1

    def test_todo_fixme_detected(self, tmp_path: Path):
        code = (
            _lines(50)
            + "\n# TODO: fix this later\n# FIXME: broken\n# HACK: workaround\n# XXX: needs review\n"
            + _lines(10)
        )
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["deferred"] >= 4

    def test_pytest_skip_detected(self, tmp_path: Path):
        code = _lines(50) + "\n@pytest.mark.skip(reason='WIP')\ndef test_x(): pass\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path, bat_density_threshold=0.01)
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["test"] >= 1


# ===================================================================
# Threshold and filtering
# ===================================================================


class TestThresholds:
    def test_below_threshold_no_finding(self, tmp_path: Path):
        """One marker in 100 lines → density 0.01 < default 0.05."""
        code = _lines(99) + "\nx = 1  # type: ignore\n"
        p = _write_file(tmp_path, "src/clean.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path)
        assert findings == []

    def test_above_threshold_finding(self, tmp_path: Path):
        """6 markers in 60 lines → density 0.1 > default 0.05."""
        markers = "\n".join(f"x{i} = 1  # type: ignore" for i in range(6))
        code = _lines(54) + "\n" + markers + "\n"
        p = _write_file(tmp_path, "src/noisy.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].metadata["bypass_density"] >= 0.05

    def test_small_file_ignored(self, tmp_path: Path):
        """Files below bat_min_loc are skipped."""
        code = "x = 1  # type: ignore\n" * 10  # 10 lines, very high density
        p = _write_file(tmp_path, "src/tiny.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path)  # default min_loc=50
        assert findings == []

    def test_custom_min_loc(self, tmp_path: Path):
        """With lowered min_loc, small files are checked."""
        code = "x = 1  # type: ignore\n" * 10
        p = _write_file(tmp_path, "src/tiny.py", code)
        findings = _run(
            [_make_pr(p)],
            repo_path=tmp_path,
            bat_min_loc=5,
            bat_density_threshold=0.5,
        )
        assert len(findings) == 1


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_test_file_ignored(self, tmp_path: Path):
        code = "x = 1  # type: ignore\n" * 60
        p = _write_file(tmp_path, "tests/test_module.py", code)
        findings = _run(
            [_make_pr(p)],
            repo_path=tmp_path,
            bat_min_loc=5,
            bat_density_threshold=0.01,
        )
        assert findings == []

    def test_unsupported_language_ignored(self, tmp_path: Path):
        pr = ParseResult(
            file_path=Path("src/main.rs"),
            language="rust",
            functions=[],
            classes=[],
            imports=[],
        )
        findings = _run([pr])
        assert findings == []

    def test_no_markers_no_finding(self, tmp_path: Path):
        code = _lines(100)
        p = _write_file(tmp_path, "src/clean.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path)
        assert findings == []

    def test_severity_high_for_double_threshold(self, tmp_path: Path):
        """Density >= 2× threshold → HIGH severity."""
        markers = "\n".join(f"x{i} = 1  # type: ignore" for i in range(12))
        code = _lines(48) + "\n" + markers + "\n"
        p = _write_file(tmp_path, "src/bad.py", code)
        findings = _run(
            [_make_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.05,
        )
        assert len(findings) == 1
        from drift.models import Severity

        assert findings[0].severity == Severity.HIGH

    def test_multiple_files_median_context(self, tmp_path: Path):
        """Median density is reported in metadata."""
        # File A: 3 markers / 60 lines
        code_a = _lines(57) + "\nx = 1  # type: ignore\ny = 2  # noqa\nz = 3  # type: ignore\n"
        p_a = _write_file(tmp_path, "src/a.py", code_a)
        # File B: 6 markers / 60 lines
        markers_b = "\n".join(f"x{i} = 1  # type: ignore" for i in range(6))
        code_b = _lines(54) + "\n" + markers_b + "\n"
        p_b = _write_file(tmp_path, "src/b.py", code_b)

        findings = _run(
            [_make_pr(p_a), _make_pr(p_b)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) >= 1
        for f in findings:
            assert "module_median_density" in f.metadata

    def test_signal_type(self, tmp_path: Path):
        markers = "\n".join(f"x{i} = 1  # type: ignore" for i in range(6))
        code = _lines(54) + "\n" + markers + "\n"
        p = _write_file(tmp_path, "src/mod.py", code)
        findings = _run([_make_pr(p)], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.BYPASS_ACCUMULATION


# ===================================================================
# TypeScript / JavaScript support
# ===================================================================


def _make_ts_pr(file_path: Path) -> ParseResult:
    """Minimal ParseResult for a TypeScript file."""
    return ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
    )


class TestTypeScriptBypass:
    def test_ts_ignore_detected(self, tmp_path: Path):
        code = _lines(50) + "\nconst x = foo(); // @ts-ignore\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.ts", code)
        findings = _run(
            [_make_ts_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1

    def test_ts_expect_error_detected(self, tmp_path: Path):
        code = _lines(50) + "\n// @ts-expect-error deliberate\nconst x = 1;\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.ts", code)
        findings = _run(
            [_make_ts_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1

    def test_eslint_disable_detected(self, tmp_path: Path):
        code = _lines(50) + "\n// eslint-disable-next-line no-any\nconst x = 1;\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.ts", code)
        findings = _run(
            [_make_ts_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["lint"] >= 1

    def test_as_any_detected(self, tmp_path: Path):
        code = _lines(50) + "\nconst x = foo() as any;\n" + _lines(10)
        p = _write_file(tmp_path, "src/module.ts", code)
        findings = _run(
            [_make_ts_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1

    def test_ts_test_file_ignored(self, tmp_path: Path):
        code = "// @ts-ignore\n" * 60
        p = _write_file(tmp_path, "src/module.spec.ts", code)
        pr = ParseResult(
            file_path=p,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
        )
        findings = _run(
            [pr],
            repo_path=tmp_path,
            bat_min_loc=5,
            bat_density_threshold=0.01,
        )
        assert findings == []

    def test_ts_nocheck_detected(self, tmp_path: Path):
        code = "// @ts-nocheck\n" + _lines(59)
        p = _write_file(tmp_path, "src/module.ts", code)
        findings = _run(
            [_make_ts_pr(p)],
            repo_path=tmp_path,
            bat_density_threshold=0.01,
        )
        assert len(findings) == 1
        assert findings[0].metadata["markers_by_category"]["type_safety"] >= 1
