from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_322_FILE = Path("extensions/telegram/src/bot-native-commands.fixture-test-support.ts")


def _write_issue_322_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_322_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "type NativeCommand = { command: string; enabled: boolean };\n"
        "type NativeCommandRegistry = { all: NativeCommand[] };\n"
        "const commandA = { command: '/start', enabled: true } as unknown as NativeCommand;\n"
        "const registry = { all: [commandA] } as unknown as NativeCommandRegistry;\n"
        "export const FIXTURE_COMMANDS = registry.all;\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_322_fixture_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_322_FILE)
    assert classify_file_context(ISSUE_322_FILE) == "test"


def test_issue_322_tsb_excludes_by_default_and_reduces_to_low_when_configured(
    tmp_path: Path,
) -> None:
    file_path = _write_issue_322_fixture(tmp_path)
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[],
        classes=[],
        imports=[],
        patterns=[],
        line_count=5,
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
    assert finding.metadata["kind_distribution"].get("double_cast", 0) == 2
