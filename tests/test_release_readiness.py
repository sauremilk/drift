"""Tests for scripts/release_readiness.py — pure aggregation logic."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gate_check  # noqa: E402
import release_readiness as rr  # noqa: E402


def _gate(gate_id: int, active: bool, status: str, reason: str = "") -> gate_check.GateResult:
    return gate_check.GateResult(gate_id, active, status, reason or "test")


def test_ready_when_all_ok_and_no_findings() -> None:
    gates = [_gate(2, True, "OK"), _gate(8, True, "OK")]
    status, reasons = rr.aggregate(
        gate_results=gates, audit_updates_required=[], findings=[]
    )
    assert status == rr.STATUS_READY
    assert reasons
    assert rr.EXIT_BY_STATUS[status] == 0


def test_blocked_when_active_gate_missing() -> None:
    gates = [_gate(3, True, "MISSING", "no changelog")]
    status, _ = rr.aggregate(gate_results=gates, audit_updates_required=[], findings=[])
    assert status == rr.STATUS_BLOCKED
    assert rr.EXIT_BY_STATUS[status] == 2


def test_blocked_when_critical_finding_present() -> None:
    gates = [_gate(8, True, "OK")]
    findings = [
        {
            "severity": "critical",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        }
    ]
    status, _ = rr.aggregate(
        gate_results=gates, audit_updates_required=[], findings=findings
    )
    assert status == rr.STATUS_BLOCKED


def test_review_when_high_finding_only() -> None:
    gates = [_gate(8, True, "OK")]
    findings = [
        {
            "severity": "high",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        }
    ]
    status, _ = rr.aggregate(
        gate_results=gates, audit_updates_required=[], findings=findings
    )
    assert status == rr.STATUS_REVIEW
    assert rr.EXIT_BY_STATUS[status] == 1


def test_review_when_audit_updates_required_only() -> None:
    gates = [_gate(8, True, "OK")]
    status, reasons = rr.aggregate(
        gate_results=gates,
        audit_updates_required=["audit_results/fmea_matrix.md"],
        findings=[],
    )
    assert status == rr.STATUS_REVIEW
    assert any("audit" in r.lower() for r in reasons)


def test_inactive_missing_gate_does_not_block() -> None:
    """Inactive gates should not affect status even if labelled MISSING."""
    gates = [_gate(7, False, "NOT_YET"), _gate(8, True, "OK")]
    status, _ = rr.aggregate(gate_results=gates, audit_updates_required=[], findings=[])
    assert status == rr.STATUS_READY


def test_blocked_takes_precedence_over_review() -> None:
    gates = [_gate(3, True, "MISSING")]
    findings = [
        {
            "severity": "high",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        }
    ]
    status, _ = rr.aggregate(
        gate_results=gates,
        audit_updates_required=["audit_results/fmea_matrix.md"],
        findings=findings,
    )
    assert status == rr.STATUS_BLOCKED


def test_low_severity_findings_do_not_trigger_review() -> None:
    gates = [_gate(8, True, "OK")]
    findings = [
        {
            "severity": "low",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        },
        {
            "severity": "info",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        },
    ]
    status, _ = rr.aggregate(
        gate_results=gates, audit_updates_required=[], findings=findings
    )
    assert status == rr.STATUS_READY


def test_exit_codes_are_distinct() -> None:
    codes = set(rr.EXIT_BY_STATUS.values())
    assert codes == {0, 1, 2}
