from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_323_FILE = Path("extensions/telegram/src/bot.media.test-utils.ts")


def _write_issue_323_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_323_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "type TelegramPhoto = { fileId: string; width: number; height: number };\n"
        "type TelegramMediaPayload = { photos: TelegramPhoto[] };\n"
        "const photo = { fileId: 'abc', width: 120, height: 80 } as unknown as TelegramPhoto;\n"
        "const media = { photos: [photo] } as unknown as TelegramMediaPayload;\n"
        "export const TEST_MEDIA = media.photos;\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_323_bot_media_test_utils_is_test_context() -> None:
    assert is_test_file(ISSUE_323_FILE)
    assert classify_file_context(ISSUE_323_FILE) == "test"


def test_issue_323_tsb_excludes_by_default_and_reduces_to_low_when_configured(
    tmp_path: Path,
) -> None:
    file_path = _write_issue_323_fixture(tmp_path)
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
