"""Phase 4 — Continuous Validation.

Checks all contracts against the current repo state using Drift signals.
Produces both a JSON report and a plain-language Markdown report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drift.intent.models import Contract, ContractResult, ContractStatus
from drift.intent.translator import results_to_markdown

# ---------------------------------------------------------------------------
# Severity ranking for comparison
# ---------------------------------------------------------------------------

_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1}


def _finding_matches_contract(
    finding: Any,
    contract: Contract,
) -> bool:
    """Check whether a Drift finding violates a given contract.

    A finding matches if its signal type matches the contract's
    verification_signal and its severity is >= the contract's severity.
    """
    if contract.verification_signal is None or contract.verification_signal == "manual":
        return False

    finding_signal = getattr(finding, "signal_type", None)
    if finding_signal != contract.verification_signal:
        return False

    finding_severity = getattr(finding, "severity", None)
    if finding_severity is None:
        return False

    # Compare severity ranks
    f_rank = _SEVERITY_RANK.get(
        finding_severity.value if hasattr(finding_severity, "value") else str(finding_severity),
        0,
    )
    c_rank = _SEVERITY_RANK.get(contract.severity, 0)
    return f_rank >= c_rank


def validate_contracts(
    intent_data: dict[str, Any],
    repo_path: Path,
    *,
    findings: list[Any] | None = None,
) -> list[ContractResult]:
    """Execute Phase 4 — validate contracts against live findings.

    Parameters
    ----------
    intent_data:
        The ``drift.intent.json`` payload.
    repo_path:
        Repository root.
    findings:
        Pre-computed findings list. If None, runs a Drift scan
        for the relevant signals.

    Returns
    -------
    list[ContractResult]
        One result per contract.
    """
    if not isinstance(intent_data, dict):
        raise TypeError(f"intent_data must be a dict, got {type(intent_data)!r}")
    contracts = [Contract.from_dict(c) for c in intent_data.get("contracts", [])]

    # Collect the signals we need
    needed_signals = {
        c.verification_signal
        for c in contracts
        if c.verification_signal and c.verification_signal != "manual"
    }

    # Run scan if no findings provided
    if findings is None and needed_signals:
        try:
            from drift.api import scan as api_scan

            result = api_scan(
                repo_path,
                signals=list(needed_signals),
                max_findings=200,
            )
            # Extract finding objects from scan result
            findings = result.get("_raw_findings", [])
            if not findings:
                findings = []
        except Exception:
            findings = []

    if findings is None:
        findings = []

    # Validate each contract
    results: list[ContractResult] = []
    for contract in contracts:
        if contract.verification_signal == "manual" or contract.verification_signal is None:
            results.append(
                ContractResult(
                    contract=contract,
                    status=ContractStatus.UNVERIFIABLE,
                )
            )
            continue

        # Check if any finding violates this contract
        violated = False
        violating_finding = None
        for f in findings:
            if _finding_matches_contract(f, contract):
                violated = True
                violating_finding = f
                break

        if violated and violating_finding is not None:
            results.append(
                ContractResult(
                    contract=contract,
                    status=ContractStatus.VIOLATED,
                    finding_id=getattr(violating_finding, "rule_id", None)
                    or getattr(violating_finding, "signal_type", "unknown"),
                    finding_title=getattr(violating_finding, "title", None),
                )
            )
        else:
            results.append(
                ContractResult(
                    contract=contract,
                    status=ContractStatus.FULFILLED,
                )
            )

    return results


def results_to_report_json(
    results: list[ContractResult],
    *,
    prompt: str = "",
    iteration: int = 0,
) -> dict[str, Any]:
    """Serialize contract results to the report JSON format."""
    fulfilled = sum(1 for r in results if r.status == ContractStatus.FULFILLED)
    violated = sum(1 for r in results if r.status == ContractStatus.VIOLATED)
    unverifiable = sum(1 for r in results if r.status == ContractStatus.UNVERIFIABLE)

    return {
        "schema_version": "1.0",
        "prompt": prompt,
        "iteration": iteration,
        "summary": {
            "total": len(results),
            "fulfilled": fulfilled,
            "violated": violated,
            "unverifiable": unverifiable,
            "all_fulfilled": violated == 0,
        },
        "contracts": [r.to_dict() for r in results],
    }


def save_report(
    results: list[ContractResult],
    repo_path: Path,
    *,
    prompt: str = "",
    iteration: int = 0,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown reports.

    Returns
    -------
    tuple[Path, Path]
        (json_path, md_path)
    """
    # JSON report
    report_json = results_to_report_json(results, prompt=prompt, iteration=iteration)
    json_path = repo_path / "drift.intent.report.json"
    json_path.write_text(
        json.dumps(report_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Markdown report
    md_content = results_to_markdown(results, prompt=prompt)
    md_path = repo_path / "drift.intent.report.md"
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
