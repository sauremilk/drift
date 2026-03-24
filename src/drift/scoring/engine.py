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


def assign_impact_scores(findings: list[Finding], weights: SignalWeights) -> None:
    """Compute and assign impact scores to each finding in-place.

    impact = signal_weight × score × (1 + log(1 + related_file_count))

    The logarithmic factor rewards findings that span many files without
    creating an unbounded multiplier for very large clusters.
    """
    weight_dict = weights.as_dict()
    for f in findings:
        key = _SIGNAL_WEIGHT_KEYS.get(f.signal_type)
        w = weight_dict.get(key, 0.1) if key else 0.1
        breadth = 1 + math.log(1 + len(f.related_files))
        f.impact = round(w * f.score * breadth, 4)


def compute_signal_scores(
    findings: list[Finding],
) -> dict[SignalType, float]:
    """Compute per-signal aggregate scores with count-dampened aggregation.

    Complexity: O(n) where n = total findings.

    Each signal's score = mean(finding_scores) * min(1, ln(1+n)/ln(1+k))
    where n = finding count and k = dampening constant.

    The logarithmic dampening prevents prolific low-confidence signals from
    dominating the composite score. A single high-score finding contributes
    less than many moderate findings — but the relationship is sublinear,
    not linear. This is calibrated via ablation study (see ADR-003).
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

    names = list(weight_fields)
    n = len(names)

    # Bounds must be feasible for a simplex of size n.
    if min_weight * n > 1.0 or max_weight * n < 1.0:
        return current_weights

    raw: dict[str, float] = {}
    for field_name in names:
        delta = ablation_deltas.get(field_name, 0.0)
        # Use absolute delta — both positive and negative indicate relevance.
        raw[field_name] = max(min_weight, abs(delta))

    total = sum(raw.values())
    if total < 0.001:
        return current_weights

    # Start from normalized raw weights and project onto the bounded simplex:
    #   sum(w)=1 and min_weight <= w_i <= max_weight
    base = {k: raw[k] / total for k in names}
    fixed: dict[str, float] = {}
    free = set(names)

    for _ in range(n + 2):
        remaining = 1.0 - sum(fixed.values())
        if remaining <= 0:
            return current_weights
        if not free:
            calibrated = dict(fixed)
            break

        base_free_total = sum(base[k] for k in free)
        if base_free_total < 0.001:
            scaled = {k: remaining / len(free) for k in free}
        else:
            factor = remaining / base_free_total
            scaled = {k: base[k] * factor for k in free}

        too_high = [k for k, v in scaled.items() if v > max_weight]
        if too_high:
            for k in too_high:
                fixed[k] = max_weight
                free.remove(k)
            continue

        too_low = [k for k, v in scaled.items() if v < min_weight]
        if too_low:
            for k in too_low:
                fixed[k] = min_weight
                free.remove(k)
            continue

        if not too_low and not too_high:
            calibrated = dict(fixed)
            calibrated.update(scaled)
            break
    else:
        return current_weights

    # Final bound safety and rounding.
    calibrated = {k: max(min_weight, min(max_weight, v)) for k, v in calibrated.items()}
    rounded = {k: round(v, 4) for k, v in calibrated.items()}

    # Adjust one non-capped key for rounding drift so sum remains near 1.0.
    drift = round(1.0 - sum(rounded.values()), 4)
    if abs(drift) > 0:
        adjustable = [
            k
            for k, v in rounded.items()
            if min_weight < v < max_weight
        ]
        target_keys = adjustable or names
        target = target_keys[0]
        rounded[target] = round(max(min_weight, min(max_weight, rounded[target] + drift)), 4)

    return current_weights.model_copy(update=rounded)
