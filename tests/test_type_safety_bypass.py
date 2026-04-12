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

    def test_test_files_can_be_included_with_reduced_severity(self, tmp_path: Path) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult, Severity
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = tmp_path / "src" / "demo.test.ts"
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

        cfg = DriftConfig(test_file_handling="reduce_severity")
        findings = TypeSafetyBypassSignal().analyze([pr], {}, cfg)
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW
        assert findings[0].metadata.get("finding_context") == "test"

    @pytest.mark.parametrize(
        "relative_path",
        [
            "extensions/whatsapp/src/test-helpers.ts",
            "src/gateway/test-http-response.ts",
        ],
    )
    def test_src_test_helpers_and_test_prefixed_paths_are_skipped(
        self, tmp_path: Path, relative_path: str
    ) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = tmp_path / Path(relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "const payload = JSON.parse(raw) as any;\n"
            "export const value = payload!;",
            encoding="utf-8",
        )

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=2,
        )

        findings = TypeSafetyBypassSignal().analyze([pr], {}, DriftConfig())
        assert findings == []

    def test_sdk_event_emitter_non_null_assertions_are_dampened(self, tmp_path: Path) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        sdk_path = tmp_path / "src" / "browser" / "pw-tools-core.interactions.ts"
        sdk_path.parent.mkdir(parents=True, exist_ok=True)
        sdk_path.write_text(
            "import { Page } from '@playwright/test';\n"
            "export function wire(page: Page): void {\n"
            "  page.on!(\"dialog\", () => {});\n"
            "  page.off!(\"dialog\", () => {});\n"
            "  page.once!(\"dialog\", () => {});\n"
            "}\n",
            encoding="utf-8",
        )

        plain_path = tmp_path / "src" / "core" / "interactions.ts"
        plain_path.parent.mkdir(parents=True, exist_ok=True)
        plain_path.write_text(
            "export function wire(page: any): void {\n"
            "  page.on!(\"dialog\", () => {});\n"
            "  page.off!(\"dialog\", () => {});\n"
            "  page.once!(\"dialog\", () => {});\n"
            "}\n",
            encoding="utf-8",
        )

        parse_results = [
            ParseResult(
                file_path=sdk_path,
                language="typescript",
                functions=[],
                classes=[],
                imports=[],
                patterns=[],
                line_count=5,
            ),
            ParseResult(
                file_path=plain_path,
                language="typescript",
                functions=[],
                classes=[],
                imports=[],
                patterns=[],
                line_count=5,
            ),
        ]

        findings = TypeSafetyBypassSignal().analyze(parse_results, {}, DriftConfig())
        assert len(findings) == 2

        by_name = {finding.file_path.name: finding for finding in findings}
        sdk_finding = by_name["pw-tools-core.interactions.ts"]
        plain_finding = by_name["interactions.ts"]

        assert sdk_finding.score < plain_finding.score
        assert sdk_finding.metadata["kind_distribution"].get("non_null_assertion_sdk", 0) == 3
        assert plain_finding.metadata["kind_distribution"].get("non_null_assertion", 0) == 3

    def test_issue_274_playwright_sdk_non_null_patterns_do_not_escalate_to_high(
        self, tmp_path: Path
    ) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult, Severity
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = (
            tmp_path
            / "extensions"
            / "browser"
            / "src"
            / "browser"
            / "pw-tools-core.interactions.ts"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "import { Page } from '@playwright/test';\n"
            "type Loc = { selector: string };\n"
            "export function wire(page: Page, resolved: Loc): void {\n"
            "  page.off!(\"framenavigated\", () => {});\n"
            "  page.on!(\"framenavigated\", () => {});\n"
            "  page.once!(\"framenavigated\", () => {});\n"
            "  page.locator(resolved.selector!);\n"
            "  page.locator(resolved.selector!);\n"
            "}\n"
            "const payload = value as unknown as Record<string, string>;\n"
            "const payload2 = value as unknown as Record<string, number>;\n",
            encoding="utf-8",
        )

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=11,
        )

        findings = TypeSafetyBypassSignal().analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        finding = findings[0]

        assert finding.severity == Severity.MEDIUM
        assert finding.score < 0.7
        assert finding.metadata["kind_distribution"].get("non_null_assertion_sdk", 0) == 5
        assert finding.metadata["kind_distribution"].get("double_cast", 0) == 2

    def test_issue_278_playwright_core_event_emitter_patterns_are_sdk_dampened(
        self, tmp_path: Path
    ) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult, Severity
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = (
            tmp_path
            / "extensions"
            / "browser"
            / "src"
            / "browser"
            / "pw-tools-core.interactions.ts"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "import type { Page } from 'playwright-core';\n"
            "export function wire(page: Page): void {\n"
            "  page.off!(\"framenavigated\", () => {});\n"
            "  page.on!(\"framenavigated\", () => {});\n"
            "  page.off!(\"framenavigated\", () => {});\n"
            "  page.on!(\"framenavigated\", () => {});\n"
            "}\n",
            encoding="utf-8",
        )

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=7,
        )

        findings = TypeSafetyBypassSignal().analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        finding = findings[0]

        assert finding.severity == Severity.LOW
        assert finding.score == 0.0
        assert finding.metadata["kind_distribution"].get("non_null_assertion_sdk", 0) == 4

    def test_issue_278_event_emitter_patterns_without_sdk_import_are_not_dampened(
        self, tmp_path: Path
    ) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = tmp_path / "src" / "browser" / "interactions.ts"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "export function wire(page: unknown): void {\n"
            "  (page as any).off!(\"framenavigated\", () => {});\n"
            "  (page as any).on!(\"framenavigated\", () => {});\n"
            "}\n",
            encoding="utf-8",
        )

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=4,
        )

        findings = TypeSafetyBypassSignal().analyze([pr], {}, DriftConfig())
        assert len(findings) == 1
        finding = findings[0]
        assert finding.metadata["kind_distribution"].get("non_null_assertion_sdk", 0) == 0
        assert finding.metadata["kind_distribution"].get("non_null_assertion", 0) == 2

    def test_issue_280_test_support_double_casts_are_treated_as_test_context(
        self, tmp_path: Path
    ) -> None:
        from drift.config import DriftConfig
        from drift.models import ParseResult, Severity
        from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

        file_path = (
            tmp_path
            / "extensions"
            / "msteams"
            / "src"
            / "monitor-handler"
            / "message-handler.test-support.ts"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "type Runtime = { logging: unknown; system: unknown; channel: unknown };\n"
            "const runtime = {\n"
            "  logging: { shouldLogVerbose: () => false },\n"
            "  system: { enqueueSystemEvent },\n"
            "  channel: { routing: { resolveAgentRoute } },\n"
            "} as unknown as Runtime;\n"
            "const deps = {\n"
            "  runtime: { error: vi.fn() } as unknown as RuntimeEnv,\n"
            "  pollStore: { recordVote: vi.fn(async () => null) } as unknown as PollStore,\n"
            "  log: { info: vi.fn(), debug: vi.fn(), error: vi.fn() } as unknown as Logger,\n"
            "};\n",
            encoding="utf-8",
        )

        pr = ParseResult(
            file_path=file_path,
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
            patterns=[],
            line_count=10,
        )

        default_findings = TypeSafetyBypassSignal().analyze([pr], {}, DriftConfig())
        assert default_findings == []

        reduced_cfg = DriftConfig(test_file_handling="reduce_severity")
        reduced_findings = TypeSafetyBypassSignal().analyze([pr], {}, reduced_cfg)
        assert len(reduced_findings) == 1

        finding = reduced_findings[0]
        assert finding.severity == Severity.LOW
        assert finding.metadata.get("finding_context") == "test"
        assert finding.metadata["kind_distribution"].get("double_cast", 0) == 4
