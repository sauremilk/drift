"""Tests for finding-context classification and policy filtering."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig, FindingContextPolicy, FindingContextRule
from drift.finding_context import (
    classify_finding_context,
    classify_path_context,
    split_findings_by_context,
)
from drift.models import Finding, Severity, SignalType


def _finding(path: str, *, signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=Severity.HIGH,
        score=0.8,
        impact=0.8,
        title="test",
        description="test",
        file_path=Path(path),
        start_line=10,
    )


def test_default_classification_two_fixture_layouts_and_generated() -> None:
    cfg = DriftConfig()

    assert classify_path_context(Path("benchmarks/corpus/src/myapp/service.py"), cfg) == "fixture"
    assert classify_path_context(Path("tests/fixtures/sample_repo/mod.py"), cfg) == "fixture"
    assert classify_path_context(Path("src/generated/client.py"), cfg) == "generated"


def test_default_classification_migration_docs_and_production() -> None:
    cfg = DriftConfig()

    assert classify_path_context(Path("src/migrations/0001_initial.py"), cfg) == "migration"
    assert classify_path_context(Path("docs/reference/config.md"), cfg) == "docs"
    assert classify_path_context(Path("tests/test_core.py"), cfg) == "test"
    assert classify_path_context(Path("src/core/service.py"), cfg) == "production"


def test_default_classification_marks_work_artifacts_and_audit_outputs_non_operational() -> None:
    cfg = DriftConfig()

    assert (
        classify_path_context(Path("work_artifacts/context_eval/export_raw.py"), cfg)
        == "fixture"
    )
    assert (
        classify_path_context(Path("audit_results/snapshots/sample_repo/service.py"), cfg)
        == "fixture"
    )


def test_override_rules_use_precedence_and_pattern_specificity() -> None:
    cfg = DriftConfig(
        finding_context=FindingContextPolicy(
            rules=[
                FindingContextRule(pattern="**/generated/**", context="generated", precedence=5),
                FindingContextRule(
                    pattern="src/generated/safe/**",
                    context="production",
                    precedence=10,
                ),
            ],
            non_operational_contexts=["generated"],
            default_context="production",
        )
    )

    assert classify_path_context(Path("src/generated/client.py"), cfg) == "generated"
    assert classify_path_context(Path("src/generated/safe/client.py"), cfg) == "production"


def test_split_findings_excludes_non_operational_by_default() -> None:
    cfg = DriftConfig()
    findings = [
        _finding("benchmarks/corpus/src/a.py"),
        _finding("src/core/b.py"),
    ]

    prioritized, excluded, counts = split_findings_by_context(
        findings,
        cfg,
        include_non_operational=False,
    )

    assert len(prioritized) == 1
    assert len(excluded) == 1
    assert counts["fixture"] == 1
    assert counts["production"] == 1


def test_split_findings_include_non_operational_opt_in() -> None:
    cfg = DriftConfig()
    findings = [
        _finding("benchmarks/corpus/src/a.py"),
        _finding("src/core/b.py"),
    ]

    prioritized, excluded, _counts = split_findings_by_context(
        findings,
        cfg,
        include_non_operational=True,
    )

    assert len(prioritized) == 2
    assert len(excluded) == 0


def test_library_context_from_signal_metadata_candidate() -> None:
    cfg = DriftConfig()
    finding = _finding(
        "src/core/contracts.py",
        signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
    )
    finding.metadata["library_context_candidate"] = True

    assert classify_finding_context(finding, cfg) == "library"


def test_split_findings_excludes_library_context_by_default() -> None:
    cfg = DriftConfig()
    library_finding = _finding(
        "src/public/api.py",
        signal_type=SignalType.DEAD_CODE_ACCUMULATION,
    )
    library_finding.metadata["library_context_candidate"] = True
    findings = [library_finding, _finding("src/core/b.py")]

    prioritized, excluded, counts = split_findings_by_context(
        findings,
        cfg,
        include_non_operational=False,
    )

    assert len(prioritized) == 1
    assert len(excluded) == 1
    assert counts["library"] == 1
    assert counts["production"] == 1


def test_adapted_header_is_classified_as_library(tmp_path: Path) -> None:
    cfg = DriftConfig()
    adapted = tmp_path / "libs" / "core" / "mustache.py"
    adapted.parent.mkdir(parents=True, exist_ok=True)
    adapted.write_text(
        '"""Adapted from https://github.com/noahmorrison/chevron.\nMIT License.\n"""\n\n'
        "def render(template: str) -> str:\n"
        "    return template\n",
        encoding="utf-8",
    )

    finding = _finding(str(adapted), signal_type=SignalType.GUARD_CLAUSE_DEFICIT)

    assert classify_finding_context(finding, cfg) == "library"
    assert finding.metadata.get("vendored_context_candidate") is True


def test_vendored_directory_is_classified_as_library(tmp_path: Path) -> None:
    cfg = DriftConfig()
    vendored = tmp_path / "third_party" / "helpers.py"
    vendored.parent.mkdir(parents=True, exist_ok=True)
    vendored.write_text(
        "def helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )

    finding = _finding(str(vendored), signal_type=SignalType.COHESION_DEFICIT)

    assert classify_finding_context(finding, cfg) == "library"
