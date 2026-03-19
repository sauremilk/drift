"""Composite drift scoring engine.

Combines individual signal scores into a weighted composite drift score
per module and for the entire repository.

See docs/adr/003-composite-scoring-model.md for design rationale.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from drift.config import SignalWeights
from drift.models import (
    Finding,
    ModuleScore,
    Severity,
    SignalType,
    severity_for_score,
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


# Re-export for backwards compat; canonical implementation in models.py
_severity_for_score = severity_for_score


# Count-dampening constant: finding counts above this value produce a
# dampening factor of ~1.0 (see ADR-003 for derivation).
_DAMPENING_K = 10


def compute_signal_scores(
    findings: list[Finding],
) -> dict[SignalType, float]:
    """Compute per-signal aggregate scores with count-dampened aggregation.

    Each signal's score = mean(finding_scores) * min(1, ln(1+n)/ln(1+k))
    where n = finding count and k = dampening constant.

    This ensures that a single finding with score 0.5 produces a lower
    signal score than 15 findings with the same mean score.
    """
    by_signal: dict[SignalType, list[float]] = defaultdict(list)
    for f in findings:
        by_signal[f.signal_type].append(f.score)

    scores: dict[SignalType, float] = {}
    for sig in SignalType:
        values = by_signal.get(sig, [])
        if values:
            mean = sum(values) / len(values)
            dampening = min(1.0, math.log(1 + len(values)) / math.log(1 + _DAMPENING_K))
            scores[sig] = round(mean * dampening, 4)

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
                f.file_path.parent.as_posix() if f.file_path.suffix else f.file_path.as_posix()
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

    return all(f.severity not in blocking for f in findings)


# ---------------------------------------------------------------------------
# Weight calibration from ablation data
# ---------------------------------------------------------------------------


def calibrate_weights(
    ablation_deltas: dict[str, float],
    current_weights: SignalWeights,
    *,
    min_weight: float = 0.02,
    max_weight: float = 0.40,
) -> SignalWeights:
    """Compute calibrated weights from ablation delta-F1 values.

    Signals whose removal causes a larger F1 drop get higher weights.
    Signals with near-zero delta get reduced to *min_weight*.

    Args:
        ablation_deltas: mapping signal_name → delta-F1 when ablated.
        current_weights: the current weight configuration.
        min_weight: floor for any signal weight.
        max_weight: ceiling for any signal weight.

    Returns:
        New ``SignalWeights`` with calibrated values summing to ~1.0.
    """
    weight_fields = type(current_weights).model_fields

    raw: dict[str, float] = {}
    for field_name in weight_fields:
        delta = ablation_deltas.get(field_name, 0.0)
        # Use absolute delta — both positive and negative indicate relevance
        raw[field_name] = max(min_weight, abs(delta))

    # Normalize to sum to 1.0
    total = sum(raw.values())
    if total < 0.001:
        return current_weights

    calibrated: dict[str, float] = {}
    for field_name, val in raw.items():
        calibrated[field_name] = val / total

    # Clamp to bounds and re-normalize iteratively
    for _ in range(5):
        clamped = {k: max(min_weight, min(max_weight, v)) for k, v in calibrated.items()}
        total_after = sum(clamped.values())
        if total_after < 0.001:
            return current_weights
        calibrated = {k: round(v / total_after, 4) for k, v in clamped.items()}
        # Check if all values are within bounds
        if all(min_weight <= v <= max_weight for v in calibrated.values()):
            break

    return current_weights.model_copy(update=calibrated)
