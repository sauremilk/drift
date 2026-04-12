from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal


def _make_fn(*, file_path: Path) -> FunctionInfo:
    return FunctionInfo(
        name="buildDynamicModel",
        file_path=file_path,
        start_line=123,
        end_line=414,
        language="typescript",
        complexity=40,
        loc=292,
        parameters=["input", "body"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=False,
    )


def _make_issue_305_fn(*, file_path: Path) -> FunctionInfo:
    return FunctionInfo(
        name="normalizeDynamicModel",
        file_path=file_path,
        start_line=67,
        end_line=85,
        language="typescript",
        complexity=12,
        loc=19,
        parameters=["params: { provider: string; model: ResolvedModelLike }"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=False,
    )


def test_issue_303_model_provider_runtime_test_support_is_test_context() -> None:
    file_path = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    assert is_test_file(file_path)
    assert classify_file_context(file_path) == "test"


def test_issue_303_eds_reduces_severity_for_model_provider_runtime_test_support() -> None:
    file_path = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[_make_fn(file_path=file_path)],
    )

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.metadata.get("finding_context") == "test"
    assert finding.finding_context == "test"
    assert finding.severity == Severity.LOW


def test_issue_305_no_eds_fp_for_normalize_dynamic_model_in_test_support() -> None:
    file_path = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    parse_result = ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[_make_issue_305_fn(file_path=file_path)],
    )

    signal = ExplainabilityDeficitSignal()

    findings_reduce = signal.analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )
    findings_exclude = signal.analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="exclude"),
    )

    assert findings_reduce == []
    assert findings_exclude == []

