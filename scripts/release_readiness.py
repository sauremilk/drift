#!/usr/bin/env python3
"""Aggregate release-readiness status across existing gate checkers.

This script does NOT implement new policy. It calls the existing gate
checkers (gate_check, risk_audit_diff) and optionally ingests a
normalized findings file from normalize_findings.py, then aggregates
to a single status line plus exit code.

Status semantics:
    READY    (exit 0) — no active MISSING gates, no high/critical findings
    REVIEW   (exit 1) — high-severity findings or audit updates needed
    BLOCKED  (exit 2) — at least one active gate is MISSING, or a critical finding

Usage:
    python scripts/release_readiness.py
    python scripts/release_readiness.py --commit-type feat
    python scripts/release_readiness.py --findings findings.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gate_check  # noqa: E402
import risk_audit_diff  # noqa: E402

STATUS_READY = "READY"
STATUS_REVIEW = "REVIEW"
STATUS_BLOCKED = "BLOCKED"

EXIT_BY_STATUS = {
    STATUS_READY: 0,
    STATUS_REVIEW: 1,
    STATUS_BLOCKED: 2,
}


def aggregate(
    *,
    gate_results: list[gate_check.GateResult],
    audit_updates_required: list[str],
    findings: list[dict],
) -> tuple[str, list[str]]:
    """Return (status, reasons) without side effects."""
    reasons: list[str] = []

    # BLOCKED conditions
    missing_gates = [g for g in gate_results if g.active and g.status == "MISSING"]
    critical_findings = [f for f in findings if f.get("severity") == "critical"]

    if missing_gates:
        for gate in missing_gates:
            reasons.append(f"gate {gate.gate} missing: {gate.reason}")
    if critical_findings:
        reasons.append(f"{len(critical_findings)} critical finding(s) open")

    if missing_gates or critical_findings:
        return STATUS_BLOCKED, reasons

    # REVIEW conditions
    high_findings = [f for f in findings if f.get("severity") == "high"]
    if high_findings:
        reasons.append(f"{len(high_findings)} high-severity finding(s) pending review")
    if audit_updates_required:
        reasons.append(
            f"{len(audit_updates_required)} audit artifact update(s) required"
        )

    if reasons:
        return STATUS_REVIEW, reasons

    reasons.append("all active gates OK, no high/critical findings, no pending audits")
    return STATUS_READY, reasons


def _load_findings(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("findings file must contain a JSON list")
    return data


def _collect_gate_results(commit_type: str) -> list[gate_check.GateResult]:
    changed_files = gate_check.collect_changed_files()
    gate6_ok, gate6_reason = gate_check._compute_gate6_ok(changed_files)
    head_lines = gate_check._git_lines("rev-parse", "HEAD")
    head_sha = head_lines[0] if head_lines else None
    last_success = gate_check._load_last_success_sha()
    return gate_check.evaluate_gates(
        changed_files,
        commit_type,
        gate6_ok=gate6_ok,
        gate6_reason=gate6_reason,
        head_sha=head_sha,
        last_success_sha=last_success,
    )


def _collect_audit_updates() -> list[str]:
    changed = risk_audit_diff._git_changed_files(staged=False)
    return risk_audit_diff.required_audit_updates(changed)


STATUS_GLYPH = {
    STATUS_READY: "OK",
    STATUS_REVIEW: "REVIEW",
    STATUS_BLOCKED: "BLOCKED",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate release-readiness status.")
    parser.add_argument(
        "--commit-type",
        choices=["feat", "fix", "chore", "signal"],
        default=None,
        help="Commit type for gate evaluation (default: infer from last commit).",
    )
    parser.add_argument(
        "--findings",
        default=None,
        help="Optional path to normalized findings JSON (from normalize_findings.py).",
    )
    args = parser.parse_args()

    commit_type = args.commit_type or gate_check._detect_commit_type()
    gate_results = _collect_gate_results(commit_type)
    audit_updates = _collect_audit_updates()

    findings: list[dict] = []
    if args.findings:
        try:
            findings = _load_findings(Path(args.findings))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: failed to load findings: {exc}", file=sys.stderr)
            return EXIT_BY_STATUS[STATUS_BLOCKED]

    status, reasons = aggregate(
        gate_results=gate_results,
        audit_updates_required=audit_updates,
        findings=findings,
    )

    print(f"Release readiness: {STATUS_GLYPH[status]}  (commit-type: {commit_type})")
    for reason in reasons:
        print(f"  - {reason}")

    print("\nGate detail:")
    for gate in gate_results:
        active = "active" if gate.active else "inactive"
        print(f"  [Gate {gate.gate}] {gate.status:<8} ({active}) - {gate.reason}")

    if audit_updates:
        print("\nRequired audit updates:")
        for item in audit_updates:
            print(f"  - {item}")

    if findings:
        print(f"\nFindings summary: {len(findings)} total")

    return EXIT_BY_STATUS[status]


if __name__ == "__main__":
    raise SystemExit(main())
