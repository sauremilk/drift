from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal


def _make_fn(
    *,
    file_path: Path,
    name: str,
    start_line: int,
    end_line: int,
    complexity: int,
    loc: int,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language="typescript",
        complexity=complexity,
        loc=loc,
        parameters=["input", "body"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=False,
    )


def _parse_result(file_path: Path) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[
            _make_fn(
                file_path=file_path,
                name="buildAssistantText",
                start_line=353,
                end_line=474,
                complexity=62,
                loc=122,
            ),
            _make_fn(
                file_path=file_path,
                name="buildResponsesPayload",
                start_line=529,
                end_line=716,
                complexity=62,
                loc=188,
            ),
            _make_fn(
                file_path=file_path,
                name="startQaMockOpenAiServer",
                start_line=718,
                end_line=842,
                complexity=36,
                loc=125,
            ),
        ],
    )


def test_issue_320_qa_lab_mock_server_is_test_context_for_relative_and_absolute_paths() -> None:
    relative = Path("extensions/qa-lab/src/mock-openai-server.ts")
    absolute = Path("C:/tmp/openclaw/extensions/qa-lab/src/mock-openai-server.ts")

    assert is_test_file(relative)
    assert classify_file_context(relative) == "test"
    assert is_test_file(absolute)
    assert classify_file_context(absolute) == "test"


def test_issue_320_eds_reduce_severity_for_all_reported_functions() -> None:
    file_path = Path("extensions/qa-lab/src/mock-openai-server.ts")
    parse_result = _parse_result(file_path)

    findings = ExplainabilityDeficitSignal().analyze([parse_result], {}, DriftConfig())

    assert len(findings) == 3
    for finding in findings:
        assert finding.metadata.get("finding_context") == "test"
        assert finding.finding_context == "test"
        assert finding.severity == Severity.LOW


def test_issue_320_eds_excludes_findings_when_test_handling_is_exclude() -> None:
    file_path = Path("extensions/qa-lab/src/mock-openai-server.ts")
    parse_result = _parse_result(file_path)

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="exclude"),
    )

    assert findings == []
