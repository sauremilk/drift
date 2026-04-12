from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal


def _make_fn(*, file_path: Path) -> FunctionInfo:
    return FunctionInfo(
        name="buildAssistantText",
        file_path=file_path,
        start_line=353,
        end_line=474,
        language="typescript",
        complexity=62,
        loc=122,
        parameters=["input", "body"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=False,
    )


def test_issue_302_qa_lab_mock_server_is_test_context() -> None:
    file_path = Path("extensions/qa-lab/src/mock-openai-server.ts")
    assert is_test_file(file_path)
    assert classify_file_context(file_path) == "test"
    assert not is_test_file(Path("extensions/qa-lab/src/index.ts"))


def test_issue_302_eds_marks_qa_lab_mock_server_as_test_context() -> None:
    file_path = Path("extensions/qa-lab/src/mock-openai-server.ts")
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[_make_fn(file_path=file_path)],
    )

    signal = ExplainabilityDeficitSignal()
    findings = signal.analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.metadata.get("finding_context") == "test"
    assert finding.finding_context == "test"
    assert finding.severity == Severity.LOW
