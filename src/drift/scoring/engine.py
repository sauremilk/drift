"""Composite drift scoring engine.

Combines individual signal scores into a weighted composite drift score
per module and for the entire repository.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from drift.config import SignalWeights
from drift.models import (
    Finding,
    ModuleScore,
    Severity,
    SignalType,
)

_SIGNAL_WEIGHT_KEYS: dict[SignalType, str] = {
    SignalType.PATTERN_FRAGMENTATION: "pattern_fragmentation",
    SignalType.ARCHITECTURE_VIOLATION: "architecture_violation",
    SignalType.MUTANT_DUPLICATE: "mutant_duplicate",
    SignalType.EXPLAINABILITY_DEFICIT: "explainability_deficit",
    SignalType.DOC_IMPL_DRIFT: "doc_impl_drift",
    SignalType.TEMPORAL_VOLATILITY: "temporal_volatility",
    SignalType.SYSTEM_MISALIGNMENT: "system_misalignment",
}


def _severity_for_score(score: float) -> Severity:
    if score >= 0.8:
        return Severity.CRITICAL
    if score >= 0.6:
        return Severity.HIGH
    if score >= 0.4:
        return Severity.MEDIUM
    if score >= 0.2:
        return Severity.LOW
    return Severity.INFO


def compute_signal_scores(
    findings: list[Finding],
) -> dict[SignalType, float]:
    """Compute per-signal aggregate scores from findings."""
    by_signal: dict[SignalType, list[float]] = defaultdict(list)
    for f in findings:
        by_signal[f.signal_type].append(f.score)

    scores: dict[SignalType, float] = {}
    for sig in SignalType:
        values = by_signal.get(sig, [])
        if values:
            scores[sig] = sum(values) / len(values)
        else:
            scores[sig] = 0.0

    return scores


def composite_score(
    signal_scores: dict[SignalType, float],
    weights: SignalWeights,
) -> float:
    """Compute weighted composite drift score."""
    weight_dict = weights.as_dict()
    total_weight = 0.0
    weighted_sum = 0.0

    for sig, score in signal_scores.items():
        key = _SIGNAL_WEIGHT_KEYS.get(sig)
        if key is None:
            continue
        w = weight_dict.get(key, 0.0)
        weighted_sum += score * w
        total_weight += w

    if total_weight < 0.001:
        return 0.0

    return round(min(1.0, weighted_sum / total_weight), 3)


def compute_module_scores(
    findings: list[Finding],
    weights: SignalWeights,
) -> list[ModuleScore]:
    """Group findings by module directory and compute per-module scores."""
    by_module: dict[str, list[Finding]] = defaultdict(list)

    for f in findings:
        if f.file_path:
            module_key = (
                f.file_path.parent.as_posix()
                if f.file_path.suffix
                else f.file_path.as_posix()
            )
        else:
            module_key = "<root>"
        by_module[module_key].append(f)

    modules: list[ModuleScore] = []

    for module_key, module_findings in by_module.items():
        signal_scores = compute_signal_scores(module_findings)
        score = composite_score(signal_scores, weights)

        ai_findings = [f for f in module_findings if f.ai_attributed]
        ai_ratio = len(ai_findings) / max(1, len(module_findings))

        modules.append(
            ModuleScore(
                path=Path(module_key),
                drift_score=score,
                signal_scores=signal_scores,
                findings=module_findings,
                ai_ratio=round(ai_ratio, 3),
            )
        )

    modules.sort(key=lambda m: m.drift_score, reverse=True)
    return modules


def severity_gate_pass(
    findings: list[Finding],
    fail_on: str,
) -> bool:
    """Check if any finding meets or exceeds the fail-on severity threshold.

    Returns True if the gate passes (no blocking findings).
    """
    threshold_map = {
        "critical": {Severity.CRITICAL},
        "high": {Severity.CRITICAL, Severity.HIGH},
        "medium": {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM},
        "low": {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW},
    }

    blocking = threshold_map.get(fail_on, {Severity.CRITICAL, Severity.HIGH})

    for f in findings:
        if f.severity in blocking:
            return False

    return True
