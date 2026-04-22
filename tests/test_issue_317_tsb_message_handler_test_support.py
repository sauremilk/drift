from __future__ import annotations

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.ingestion.ts_parser import tree_sitter_available
from drift.models import ParseResult, Severity
from drift.signals.type_safety_bypass import TypeSafetyBypassSignal

ISSUE_317_FILE = Path("extensions/msteams/src/monitor-handler/message-handler.test-support.ts")

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)


def _write_issue_317_fixture(tmp_path: Path) -> Path:
    file_path = tmp_path / ISSUE_317_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "// Test-support stubs for message-handler integration tests.\n"
        "const runtime = {} as any;\n"
        "const env = {} as any;\n"
        "const pollStore = {} as any;\n"
        "const log = {} as any;\n"
        "export { runtime, env, pollStore, log };\n",
        encoding="utf-8",
    )
    return file_path


def test_issue_317_message_handler_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_317_FILE)
    assert classify_file_context(ISSUE_317_FILE) == "test"


@needs_tree_sitter
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
        line_count=6,
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
    assert finding.metadata["kind_distribution"].get("as_any", 0) == 4
