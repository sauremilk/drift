"""Regression tests for actionable copilot-context wording (Issue #125)."""

from __future__ import annotations

import datetime
from pathlib import Path

from drift.copilot_context import generate_instructions
from drift.models import Finding, RepoAnalysis, Severity, SignalType


def _analysis_from_findings(findings: list[Finding]) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=max((f.score for f in findings), default=0.0),
        findings=findings,
    )


def test_pfs_rule_includes_exemplar_and_deviation_locations() -> None:
    findings = [
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.8,
            title="error_handling: 2 variants in services/",
            description="Pattern fragmentation",
            fix=(
                "Consolidate to the dominant pattern (3x, exemplar: services/a.py:10). "
                "Deviations: services/b.py:20 (handle), services/c.py:30 (fallback)."
            ),
            file_path=Path("services"),
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.7,
            title="error_handling: 2 variants in services/",
            description="Pattern fragmentation",
            fix=(
                "Consolidate to the dominant pattern (2x, exemplar: services/a.py:10). "
                "Deviations: services/d.py:40 (handle)."
            ),
            file_path=Path("services"),
        ),
    ]

    output = generate_instructions(_analysis_from_findings(findings))

    assert "### Code Pattern Consistency (PFS)" in output
    assert "exemplar: services/a.py:10" in output
    assert "Deviations: services/b.py:20" in output


def test_nbv_rule_includes_contract_specific_suggestion_and_location() -> None:
    findings = [
        Finding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.8,
            title="Naming contract violation: check_access()",
            description="contract mismatch",
            fix=(
                "'check_access()' at src/security.py:12 does not satisfy 'check_' naming "
                "contract. Suggestion: implement a rejection path (raise or return "
                "False/None), or rename the function to match non-validating behavior."
            ),
            file_path=Path("src/security.py"),
            start_line=12,
            end_line=20,
        ),
        Finding(
            signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.7,
            title="Naming contract violation: check_scope()",
            description="contract mismatch",
            fix=(
                "'check_scope()' at src/security.py:30 does not satisfy 'check_' naming "
                "contract. Suggestion: implement a rejection path (raise or return "
                "False/None), or rename the function to match non-validating behavior."
            ),
            file_path=Path("src/security.py"),
            start_line=30,
            end_line=36,
        ),
    ]

    output = generate_instructions(_analysis_from_findings(findings))

    assert "### Naming Conventions (NBV)" in output
    assert "src/security.py:12" in output
    assert "raise or return False/None" in output
