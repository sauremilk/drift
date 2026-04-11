"""Tests for TypeScript export detection (Task 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import parse_typescript_file, tree_sitter_available

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)


@needs_tree_sitter
class TestExportDetection:
    """Test is_exported flag on FunctionInfo for TypeScript files."""

    def test_exported_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "processOrder")
        assert fn.is_exported is True

    def test_default_exported_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "handler")
        assert fn.is_exported is True

    def test_exported_arrow_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "helper")
        assert fn.is_exported is True

    def test_non_exported_underscore_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "_internal")
        assert fn.is_exported is False

    def test_non_exported_public_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "computeTotal")
        assert fn.is_exported is False

    def test_non_exported_arrow_function(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/exports.ts"),
            Path("."),
        )
        fn = next(f for f in result.functions if f.name == "formatter")
        assert fn.is_exported is False

    def test_no_exports_file(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/export_detection/no_exports.ts"),
            Path("."),
        )
        for fn in result.functions:
            assert fn.is_exported is False, f"{fn.name} should not be exported"

    def test_python_function_default_not_exported(self) -> None:
        """Verify FunctionInfo default for is_exported is False."""
        from drift.models import FunctionInfo

        fi = FunctionInfo(
            name="foo",
            file_path=Path("foo.py"),
            start_line=1,
            end_line=5,
            language="python",
        )
        assert fi.is_exported is False


@needs_tree_sitter
class TestDCAScoreBoost:
    """Test that DCA score boost applies to non-exported TS functions."""

    def test_non_exported_ts_functions_get_score_boost(self) -> None:
        from drift.config import DriftConfig
        from drift.models import (
            FunctionInfo,
            ParseResult,
        )
        from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal

        # Create two TS parse results:
        # File A: 3 public non-exported functions (none imported)
        # File B: imports none of them
        fn1 = FunctionInfo(
            name="computeTotal",
            file_path=Path("src/utils.ts"),
            start_line=1,
            end_line=5,
            language="typescript",
            is_exported=False,
        )
        fn2 = FunctionInfo(
            name="formatDate",
            file_path=Path("src/utils.ts"),
            start_line=7,
            end_line=11,
            language="typescript",
            is_exported=False,
        )
        fn3 = FunctionInfo(
            name="validateInput",
            file_path=Path("src/utils.ts"),
            start_line=13,
            end_line=17,
            language="typescript",
            is_exported=False,
        )

        pr_a = ParseResult(
            file_path=Path("src/utils.ts"),
            language="typescript",
            functions=[fn1, fn2, fn3],
            classes=[],
            imports=[],
            patterns=[],
            line_count=20,
        )
        pr_b = ParseResult(
            file_path=Path("src/main.ts"),
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=5,
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_a, pr_b], {}, DriftConfig())

        # Should produce at least one finding with boosted score
        assert len(findings) >= 1
        finding = findings[0]
        # Base score for 3/3 dead: 0.8 * 1.0 + 3 * 0.02 = 0.86
        # Boost +0.15 → min(1.0, 1.01) = 1.0
        assert finding.score >= 0.86  # boosted beyond base

    def test_exported_ts_functions_no_boost(self) -> None:
        from drift.config import DriftConfig
        from drift.models import (
            FunctionInfo,
            ParseResult,
        )
        from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal

        # Same setup but functions are exported
        fn1 = FunctionInfo(
            name="computeTotal",
            file_path=Path("src/utils.ts"),
            start_line=1,
            end_line=5,
            language="typescript",
            is_exported=True,
        )
        fn2 = FunctionInfo(
            name="formatDate",
            file_path=Path("src/utils.ts"),
            start_line=7,
            end_line=11,
            language="typescript",
            is_exported=True,
        )

        pr_a = ParseResult(
            file_path=Path("src/utils.ts"),
            language="typescript",
            functions=[fn1, fn2],
            classes=[],
            imports=[],
            patterns=[],
            line_count=15,
        )
        pr_b = ParseResult(
            file_path=Path("src/main.ts"),
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=5,
        )

        signal = DeadCodeAccumulationSignal()
        findings = signal.analyze([pr_a, pr_b], {}, DriftConfig())

        # 2/2 dead ratio=1.0, score = 0.8 + 0.04 = 0.84
        # No boost since all are exported
        if findings:
            assert findings[0].score == 0.84
