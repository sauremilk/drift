"""Tests for TS naming consistency checks in NamingContractViolation (Task 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import parse_typescript_file, tree_sitter_available

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)

FIXTURES = Path("tests/fixtures/typescript/naming_consistency")


@needs_tree_sitter
class TestIPrefixConsistency:
    """I-prefix is a TS style choice and should not trigger NBV findings."""

    def test_dominant_i_prefix_does_not_flag_outliers(self) -> None:
        from drift.config import DriftConfig
        from drift.signals.naming_contract_violation import NamingContractViolationSignal

        pr = parse_typescript_file(FIXTURES / "i_prefix_dominant.ts", Path("."))
        signal = NamingContractViolationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        iprefix_findings = [
            f for f in findings if "I-prefix" in f.title or "missing I-prefix" in f.title
        ]
        assert iprefix_findings == []

    def test_consistent_no_prefix_no_findings(self) -> None:
        from drift.config import DriftConfig
        from drift.signals.naming_contract_violation import NamingContractViolationSignal

        pr = parse_typescript_file(FIXTURES / "no_prefix_consistent.ts", Path("."))
        signal = NamingContractViolationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        iprefix_findings = [f for f in findings if "I-prefix" in f.title]
        assert len(iprefix_findings) == 0


@needs_tree_sitter
class TestEnumCasingConsistency:
    """Test enum member casing consistency detection."""

    def test_mixed_enum_casing_flagged(self) -> None:
        from drift.config import DriftConfig
        from drift.signals.naming_contract_violation import NamingContractViolationSignal

        pr = parse_typescript_file(FIXTURES / "enum_mixed_casing.ts", Path("."))
        signal = NamingContractViolationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        enum_findings = [f for f in findings if "mixed member casing" in f.title]
        assert len(enum_findings) == 1


@needs_tree_sitter
class TestGenericParameterNaming:
    """Generic naming style mix is not treated as drift (Issue #219)."""

    def test_mixed_generics_not_flagged(self) -> None:
        from drift.config import DriftConfig
        from drift.signals.naming_contract_violation import NamingContractViolationSignal

        pr = parse_typescript_file(FIXTURES / "generics_mixed.ts", Path("."))
        signal = NamingContractViolationSignal()
        findings = signal.analyze([pr], {}, DriftConfig())

        generic_findings = [f for f in findings if "generic parameter" in f.title.lower()]
        assert generic_findings == []
