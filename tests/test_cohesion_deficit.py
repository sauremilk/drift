"""Tests for Cohesion Deficit signal."""

from pathlib import Path

from drift.config import DriftConfig
from drift.models import ClassInfo, FunctionInfo, ParseResult, SignalType
from drift.signals.cohesion_deficit import CohesionDeficitSignal


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