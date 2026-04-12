from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_319_FILE = Path("src/commands/status.test-support.ts")


def _write_issue_319_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_319_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "import { vi } from 'vitest';\n"
        "type StatusSummary = { ok: boolean };\n"
        "type MemoryStatusSnapshot = { updatedAt: number };\n"
        "type ChannelHealth = { connected: boolean };\n"
        "const summary = { ok: true } as unknown as StatusSummary;\n"
        "const snapshot = { updatedAt: Date.now() } as unknown as MemoryStatusSnapshot;\n"
        "const channel = { connected: vi.fn() } as unknown as ChannelHealth;\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_319_status_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_319_FILE)
    assert classify_file_context(ISSUE_319_FILE) == "test"


def test_issue_319_tsb_excludes_by_default_and_reduces_to_low_when_configured(
    tmp_path: Path,
) -> None:
    file_path = _write_issue_319_fixture(tmp_path)
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
        patterns=[],
        line_count=7,
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
    assert finding.metadata["kind_distribution"].get("double_cast", 0) == 3
