from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal

ISSUE_314_FILE = Path(
    "src/agents/pi-embedded-runner/run/attempt.spawn-workspace.test-support.ts"
)


def _exported_ts_function(name: str, line: int) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=ISSUE_314_FILE,
        start_line=line,
        end_line=line + 3,
        language="typescript",
        complexity=1,
        loc=4,
        is_exported=True,
    )


def test_issue_314_attempt_spawn_workspace_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_314_FILE)
    assert classify_file_context(ISSUE_314_FILE) == "test"


def test_issue_314_dca_reduces_test_support_finding_to_low() -> None:
    parse_result = ParseResult(
        file_path=ISSUE_314_FILE,
        language="typescript",
        functions=[
            _exported_ts_function("createSubscriptionMock", 623),
            _exported_ts_function("cleanupTempPaths", 650),
            _exported_ts_function("createDefaultEmbeddedSession", 701),
            _exported_ts_function("createContextEngineAttemptRunner", 742),
            _exported_ts_function("createModelProviderRuntime", 781),
        ],
        imports=[],
    )

    findings = DeadCodeAccumulationSignal().analyze([parse_result], {}, DriftConfig())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path == ISSUE_314_FILE
    assert finding.severity == Severity.LOW
    assert finding.metadata.get("finding_context") == "test"
    assert finding.metadata.get("dead_count") == 5
