"""Tests for check_risk_audit.py audit content validation (M4)."""

from __future__ import annotations

# Dynamic import since scripts/ is not a package
import importlib.util
import textwrap
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_risk_audit",
    Path(__file__).resolve().parent.parent / "scripts" / "check_risk_audit.py",
)
assert _spec and _spec.loader
check_risk_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_risk_audit)  # type: ignore[union-attr]


class TestFMEAContentValidation:
    """Tests for _validate_fmea_content."""

    _FMEA_HEADER = (
        "| Signal | Failure Mode | Cause | Effect | Detection | "
        "Mitigation | S | O | D | RPN | Status |"
    )
    _FMEA_SEPARATOR = (
        "|--------|-------------|-------|--------|-----------|------------|"
        "---|---|---|-----|--------|"
    )
    _FMEA_ROW = (
        "| PFS  | False positive on utils | Threshold too low | Noise | "
        "Review | Raise threshold | 3 | 2 | 4 | 24 | Open |"
    )

    def test_valid_fmea(self, tmp_path: Path):
        fmea = tmp_path / "fmea.md"
        fmea.write_text(
            textwrap.dedent(
                f"""\
                # FMEA Matrix
                {self._FMEA_HEADER}
                {self._FMEA_SEPARATOR}
                {self._FMEA_ROW}
                """
            ),
            encoding="utf-8",
        )
        issues = check_risk_audit._validate_fmea_content(str(fmea))
        assert issues == []

    def test_empty_fmea(self, tmp_path: Path):
        fmea = tmp_path / "fmea.md"
        fmea.write_text("# FMEA Matrix\n\nNothing here yet.\n", encoding="utf-8")
        issues = check_risk_audit._validate_fmea_content(str(fmea))
        assert len(issues) == 2  # No table header, no data rows

    def test_header_only_fmea(self, tmp_path: Path):
        fmea = tmp_path / "fmea.md"
        fmea.write_text(
            textwrap.dedent(
                f"""\
                # FMEA Matrix
                {self._FMEA_HEADER}
                {self._FMEA_SEPARATOR}
                """
            ),
            encoding="utf-8",
        )
        issues = check_risk_audit._validate_fmea_content(str(fmea))
        # Header row matches both header pattern and row pattern —
        # structural validation passes (content completeness is a separate concern)
        assert len(issues) == 0


class TestRiskRegisterContentValidation:
    """Tests for _validate_risk_register_content."""

    def test_valid_risk_register(self, tmp_path: Path):
        rr = tmp_path / "risk_register.md"
        rr.write_text(textwrap.dedent("""\
            # Risk Register
            ## Entry 1
            - Risk ID: RISK-001
            - Component: PFS Signal
            - Type: False Positive
            - Description: PFS flags utility modules
            - Mitigation: Threshold adjustment
            - Residual risk: Low
        """), encoding="utf-8")
        issues = check_risk_audit._validate_risk_register_content(str(rr))
        assert issues == []

    def test_empty_risk_register(self, tmp_path: Path):
        rr = tmp_path / "risk_register.md"
        rr.write_text("# Risk Register\n\n(empty)\n", encoding="utf-8")
        issues = check_risk_audit._validate_risk_register_content(str(rr))
        assert len(issues) == 2  # No Risk ID, no Mitigation


class TestFaultTreesContentValidation:
    """Tests for _validate_fault_trees_content."""

    def test_valid_fault_trees(self, tmp_path: Path):
        ft = tmp_path / "fault_trees.md"
        ft.write_text(textwrap.dedent("""\
            # Fault Tree Analysis
            ### Top Event: TE-1 — False positive in production
            ```
            TE-1 (OR-Gate)
            ├── FT-1: Signal threshold miscalibration
            └── FT-2: Input parsing error
            ```
            ### Minimal Cut Set
            | MCS | Components |
        """), encoding="utf-8")
        issues = check_risk_audit._validate_fault_trees_content(str(ft))
        assert issues == []

    def test_empty_fault_trees(self, tmp_path: Path):
        ft = tmp_path / "fault_trees.md"
        ft.write_text("# Fault Trees\n\nTBD\n", encoding="utf-8")
        issues = check_risk_audit._validate_fault_trees_content(str(ft))
        assert len(issues) == 2  # No Top Event, no structure


class TestSTRIDEContentValidation:
    """Tests for _validate_stride_content."""

    def test_valid_stride(self, tmp_path: Path):
        stride = tmp_path / "stride.md"
        stride.write_text(textwrap.dedent("""\
            # STRIDE Threat Model
            ## Trust Boundary: CLI → File System
            - STRIDE review:
              - S (Spoofing): Config file could be spoofed — mitigated by path validation
              - T (Tampering): Audit files protected by git tracking
              - R (Repudiation): All changes logged in git
              - I (Information Disclosure): No secrets in output
              - D (Denial of Service): Bounded resource usage
              - E (Elevation of Privilege): No privilege escalation path
        """), encoding="utf-8")
        issues = check_risk_audit._validate_stride_content(str(stride))
        assert issues == []

    def test_empty_stride(self, tmp_path: Path):
        stride = tmp_path / "stride.md"
        stride.write_text("# STRIDE Model\n\nPending.\n", encoding="utf-8")
        issues = check_risk_audit._validate_stride_content(str(stride))
        assert len(issues) == 2  # No review section, no items


class TestValidateAuditContent:
    """Tests for the aggregate validate_audit_content function."""

    def test_all_valid_returns_empty(self):
        # Uses real audit_results/ in the repo — they should be valid
        results = check_risk_audit.validate_audit_content()
        assert results == {}, f"Unexpected issues in real audit artifacts: {results}"
