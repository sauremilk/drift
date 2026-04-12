from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_317_FILE = Path("extensions/msteams/src/monitor-handler/message-handler.test-support.ts")


def _write_issue_317_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_317_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "import { vi } from 'vitest';\n"
        "type PluginRuntime = { logging: unknown; system: unknown; channel: unknown };\n"
        "type RuntimeEnv = { error: unknown };\n"
        "type PollStore = { recordVote: unknown };\n"
        "type Logger = { info: unknown; debug: unknown; error: unknown };\n"
        "const runtime = {\n"
        "  logging: { shouldLogVerbose: () => false },\n"
        "  system: {},\n"
        "  channel: {},\n"
        "} as unknown as PluginRuntime;\n"
        "const deps = {\n"
        "  runtime: { error: vi.fn() } as unknown as RuntimeEnv,\n"
        "  pollStore: { recordVote: vi.fn(async () => null) } as unknown as PollStore,\n"
        "  log: { info: vi.fn(), debug: vi.fn(), error: vi.fn() } as unknown as Logger,\n"
        "};\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_317_message_handler_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_317_FILE)
    assert classify_file_context(ISSUE_317_FILE) == "test"


def test_issue_317_tsb_excludes_by_default_and_reduces_to_low_when_configured(
    tmp_path: Path,
) -> None:
    file_path = _write_issue_317_fixture(tmp_path)
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
        patterns=[],
        line_count=16,
    )

    default_findings = TypeSafetyBypassSignal().analyze([parse_result], {}, DriftConfig())
    assert default_findings == []

    reduced_findings = TypeSafetyBypassSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert len(reduced_findings) == 1
    finding = reduced_findings[0]
    assert finding.severity == Severity.LOW
    assert finding.finding_context == "test"
    assert finding.metadata.get("finding_context") == "test"
    assert finding.metadata["kind_distribution"].get("double_cast", 0) == 4
