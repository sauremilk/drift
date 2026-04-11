"""Tests for TypeSafetyBypass signal (Task 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import tree_sitter_available

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)

FIXTURES = Path("tests/fixtures/typescript/type_safety_bypass")


@needs_tree_sitter
class TestBypassCounting:
    """Test _count_bypasses helper."""

    def test_clean_file_no_bypasses(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = FIXTURES.joinpath("clean.ts").read_text(encoding="utf-8")
        bypasses = _count_bypasses(source, "typescript")
        assert len(bypasses) == 0

    def test_moderate_file_has_bypasses(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = FIXTURES.joinpath("moderate.ts").read_text(encoding="utf-8")
        bypasses = _count_bypasses(source, "typescript")
        assert len(bypasses) >= 3

    def test_severe_file_many_bypasses(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = FIXTURES.joinpath("severe.ts").read_text(encoding="utf-8")
        bypasses = _count_bypasses(source, "typescript")
        assert len(bypasses) >= 8

    def test_as_any_detected(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = "const x = JSON.parse(data) as any;"
        bypasses = _count_bypasses(source, "typescript")
        kinds = [b["kind"] for b in bypasses]
        assert "as_any" in kinds

    def test_non_null_detected(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = 'const el = document.getElementById("root")!;'
        bypasses = _count_bypasses(source, "typescript")
        kinds = [b["kind"] for b in bypasses]
        assert "non_null_assertion" in kinds

    def test_ts_ignore_detected(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = "// @ts-ignore\nconst x = broken + 1;"
        bypasses = _count_bypasses(source, "typescript")
        kinds = [b["kind"] for b in bypasses]
        assert "ts_ignore" in kinds

    def test_ts_expect_error_detected(self) -> None:
        from drift.signals.type_safety_bypass import _count_bypasses

        source = '// @ts-expect-error\nconst y: number = "str";'
        bypasses = _count_bypasses(source, "typescript")
        kinds = [b["kind"] for b in bypasses]
        assert "ts_expect_error" in kinds


@needs_tree_sitter
class TestTypeSafetyBypassSignal:
    """Test the full signal."""

    def test_clean_file_no_findings(self) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        pr = ParseResult(
            file_path=FIXTURES / "clean.ts",
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=20,
        )

        signal = TypeSafetyBypassSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_moderate_file_produces_finding(self) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        pr = ParseResult(
            file_path=FIXTURES / "moderate.ts",
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=20,
        )

        signal = TypeSafetyBypassSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].score > 0
        assert findings[0].score <= 1.0

    def test_severe_file_high_score(self) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        pr = ParseResult(
            file_path=FIXTURES / "severe.ts",
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=35,
        )

        signal = TypeSafetyBypassSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].score >= 0.8

    def test_python_file_no_findings(self) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        pr = ParseResult(
            file_path=Path("main.py"),
            language="python",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=10,
        )

        signal = TypeSafetyBypassSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_signal_type(self) -> None:
        from drift.models import SignalType
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        signal = TypeSafetyBypassSignal()
        assert signal.signal_type == SignalType.TYPE_SAFETY_BYPASS

    def test_signal_registered(self) -> None:
        from drift.signals.base import _SIGNAL_REGISTRY
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        assert TypeSafetyBypassSignal in _SIGNAL_REGISTRY

    @pytest.mark.parametrize(
        "relative_path",
        [
            "src/user.test.ts",
            "src/user.spec.tsx",
            "src/__tests__/user.ts",
            "src/__mocks__/user.ts",
        ],
    )
    def test_test_and_mock_paths_are_skipped(self, tmp_path: Path, relative_path: str) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = tmp_path / Path(relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("const x = JSON.parse(data) as any;", encoding="utf-8")

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=1,
        )

        signal = TypeSafetyBypassSignal()
        findings = signal.analyze([pr], {}, DriftConfig())
        assert findings == []
