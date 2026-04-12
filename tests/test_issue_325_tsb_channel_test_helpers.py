from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_325_FILE = Path("src/commands/channel-test-helpers.ts")


def _write_issue_325_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_325_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "type Setup = { channel: { id: string }; guild: { id: string } };\n"
        "type Ready = { channelId: string; guildId: string };\n"
        "export function asReady(setup?: Setup): Ready {\n"
        "  const channelId = setup!.channel.id;\n"
        "  const guildId = setup!.guild.id;\n"
        "  return { channelId, guildId };\n"
        "}\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_325_channel_test_helpers_is_test_context() -> None:
    assert is_test_file(ISSUE_325_FILE)
    assert classify_file_context(ISSUE_325_FILE) == "test"


def test_issue_325_tsb_excludes_by_default_and_reduces_to_low_when_configured(
    tmp_path: Path,
) -> None:
    file_path = _write_issue_325_fixture(tmp_path)
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
    assert finding.metadata["kind_distribution"].get("non_null_assertion", 0) == 2
