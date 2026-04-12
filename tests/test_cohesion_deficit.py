"""Tests for Cohesion Deficit signal."""

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import ClassInfo, FunctionInfo, ParseResult, SignalType
from drift.precision import (
    ensure_signals_registered,
    has_matching_finding,
    run_fixture,
)
from drift.signals.cohesion_deficit import CohesionDeficitSignal
from tests.fixtures.ground_truth import FIXTURES_BY_SIGNAL, GroundTruthFixture


def _function(name: str, file_path: str, line: int) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 6,
        language="python",
        complexity=4,
        loc=7,
    )


def _class(name: str, file_path: str, line: int, methods: list[FunctionInfo]) -> ClassInfo:
    return ClassInfo(
        name=name,
        file_path=Path(file_path),
        start_line=line,
        end_line=line + 20,
        language="python",
        methods=methods,
    )


def test_cod_true_positive_fixture() -> None:
    """Utility-dump style file with unrelated units should trigger COD."""
    file_path = "utils/misc_helpers.py"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=[
            _function("parse_invoice_xml", file_path, 10),
            _function("send_slack_alert", file_path, 30),
            _function("resize_profile_image", file_path, 50),
            _function("compile_tax_report", file_path, 70),
            _function("decrypt_api_secret", file_path, 90),
        ],
        classes=[
            _class(
                "ExperimentScheduler",
                file_path,
                120,
                methods=[_function("ExperimentScheduler.enqueue_trial", file_path, 125)],
            )
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.signal_type == SignalType.COHESION_DEFICIT
    assert finding.score >= 0.35
    assert finding.metadata["isolated_count"] >= 3


def test_cod_true_negative_fixture() -> None:
    """Cohesive tax-focused file should not trigger COD."""
    file_path = "finance/tax_calculations.py"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=[
            _function("calculate_tax_base", file_path, 10),
            _function("calculate_tax_rate", file_path, 30),
            _function("validate_tax_inputs", file_path, 50),
            _function("format_tax_summary", file_path, 70),
            _function("round_tax_amount", file_path, 90),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_cod_ignores_tiny_files() -> None:
    """Small files with too few semantic units are ignored to reduce noise."""
    file_path = "helpers/tiny.py"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=[
            _function("parse_token", file_path, 5),
            _function("send_mail", file_path, 15),
            _function("hash_password", file_path, 25),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_cod_logger_module_is_not_flagged() -> None:
    """Logger facade modules should not be treated as cohesion deficits."""
    file_path = "sdk/logger.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("noop", file_path, 10),
            _function("setMatrixConsoleLogging", file_path, 20),
            _function("formatMessage", file_path, 30),
            _function("trace", file_path, 40),
            _function("debug", file_path, 50),
            _function("info", file_path, 60),
            _function("warn", file_path, 70),
            _function("error", file_path, 80),
            _function("setLogger", file_path, 90),
            _function("log", file_path, 100),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_cod_utility_filename_still_flags_clear_deficit() -> None:
    """Utility filename hints should dampen noise but keep clear deficits detectable."""
    file_path = "helpers/misc_utils.py"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="python",
        functions=[
            _function("parse_invoice_xml", file_path, 10),
            _function("send_slack_alert", file_path, 30),
            _function("resize_profile_image", file_path, 50),
            _function("compile_tax_report", file_path, 70),
            _function("decrypt_api_secret", file_path, 90),
            _function("provision_ci_runner", file_path, 110),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert len(findings) == 1
    assert findings[0].metadata["utility_filename_hint"] is True


def test_cod_plugin_register_family_module_is_not_flagged() -> None:
    """Plugin registration families under extensions/*/src should not trigger COD."""
    file_path = "extensions/anthropic/src/provider_registration.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("registerProvider", file_path, 10),
            _function("registerModels", file_path, 20),
            _function("registerTools", file_path, 30),
            _function("registerActions", file_path, 40),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_cod_plugin_create_family_helpers_are_not_flagged() -> None:
    """create*-heavy plugin helpers are one concern and should avoid COD FPs."""
    file_path = "extensions/memory-wiki/src/test-helpers.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("createMemoryWikiTestHarness", file_path, 10),
            _function("createTempDir", file_path, 20),
            _function("createVault", file_path, 30),
            _function("createPluginApi", file_path, 40),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_cod_filename_domain_token_dampens_format_module() -> None:
    """Filename domain token (format.ts) should dampen typed utility module noise."""
    file_path = "extensions/discord/src/format.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("formatEmbed", file_path, 10),
            _function("formatMessage", file_path, 20),
            _function("formatAttachment", file_path, 30),
            _function("formatComponent", file_path, 40),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_issue_283_test_harness_file_is_ignored() -> None:
    """Issue #283: explicit .test-harness naming should skip COD evaluation."""
    file_path = "src/auto-reply/reply/dispatch-from-config.shared.test-harness.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("parseGenericThreadSessionInfo", file_path, 10),
            _function("createDispatcher", file_path, 20),
            _function("buildAbortDecision", file_path, 30),
            _function("formatRouteReplyResult", file_path, 40),
            _function("wireDiagnosticLogging", file_path, 50),
            _function("registerHookRunner", file_path, 60),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


def test_issue_284_test_helpers_file_is_ignored() -> None:
    """Issue #284: explicit .test-helpers naming should skip COD evaluation."""
    file_path = "src/config/plugin-auto-enable.test-helpers.ts"
    parse_result = ParseResult(
        file_path=Path(file_path),
        language="typescript",
        functions=[
            _function("resetPluginAutoEnableTestState", file_path, 10),
            _function("makeTempDir", file_path, 20),
            _function("makeIsolatedEnv", file_path, 30),
            _function("writePluginManifestFixture", file_path, 40),
            _function("wireRegistryCache", file_path, 50),
            _function("ensurePluginLifecycle", file_path, 60),
        ],
    )

    findings = CohesionDeficitSignal().analyze([parse_result], {}, DriftConfig())
    assert findings == []


# ---------------------------------------------------------------------------
# Parametrized ground-truth fixture tests
# ---------------------------------------------------------------------------

ensure_signals_registered()

_COD_FIXTURES = FIXTURES_BY_SIGNAL.get(SignalType.COHESION_DEFICIT, [])


@pytest.mark.parametrize(
    "fixture",
    _COD_FIXTURES,
    ids=[f.name for f in _COD_FIXTURES],
)
def test_cod_ground_truth(fixture: GroundTruthFixture, tmp_path: Path) -> None:
    """Verify COD ground-truth fixtures produce expected findings."""
    findings, _warnings = run_fixture(
        fixture, tmp_path, signal_filter={SignalType.COHESION_DEFICIT}
    )
    for exp in fixture.expected:
        if exp.signal_type != SignalType.COHESION_DEFICIT:
            continue
        detected = has_matching_finding(findings, exp)
        if exp.should_detect:
            assert detected, (
                f"[FN] {fixture.name}: expected COD at {exp.file_path} "
                f"but not found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
        else:
            assert not detected, (
                f"[FP] {fixture.name}: did NOT expect COD at {exp.file_path} "
                f"but found. Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
