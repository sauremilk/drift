"""Composite drift scoring engine.

Combines individual signal scores into a weighted composite drift score
per module and for the entire repository.

See docs/adr/003-composite-scoring-model.md for design rationale.
"""

from __future__ import annotations

import fnmatch
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from drift.config import PathOverride, SignalWeights
from drift.models import (
    Finding,
    ModuleScore,
    Severity,
    SignalType,
    severity_for_score,
)

# Generated from SignalType enum — adding a new SignalType auto-registers
# its weight key without a manual dict entry.
# For plugin signals (str, not SignalType), the key IS the value.
_SIGNAL_WEIGHT_KEYS: dict[str, str] = {str(sig): str(sig) for sig in SignalType}


# Re-export for backwards compat; canonical implementation in models.py
_severity_for_score = severity_for_score


# Count-dampening constant: finding counts above this value produce a
# dampening factor of ~1.0 (see ADR-003 for derivation, ADR-041 for k=20).
_DAMPENING_K = 20

# Breadth-multiplier ceiling (ADR-041): caps the log-based breadth factor
# so that very large related_file clusters don't inflate impact unboundedly.
_BREADTH_CAP = 4.0


def assign_impact_scores(findings: list[Finding], weights: SignalWeights) -> None:
    """Compute and assign impact scores to each finding in-place.

    impact = signal_weight × score × min(BREADTH_CAP, 1 + log(1 + related_file_count))

    The logarithmic factor rewards findings that span many files without
    creating an unbounded multiplier for very large clusters.  The cap
    prevents extreme inflation beyond ~50 related files (see ADR-041).

    Also computes ``score_contribution`` — the fraction of the composite
    score attributable to this finding.  Useful for prioritising which
    fixes reduce the overall drift score the most.
    """
    weight_dict = weights.as_dict()
    total_weight = sum(weight_dict.values())

    for f in findings:
        key = _SIGNAL_WEIGHT_KEYS.get(f.signal_type, f.signal_type)
        w = weight_dict.get(key, 0.1)
        breadth = min(_BREADTH_CAP, 1 + math.log(1 + len(f.related_files)))
        f.impact = round(w * f.score * breadth, 4)

        # score_contribution: estimated share of the composite score
        if total_weight > 0.001:
            f.score_contribution = round((w * f.score) / total_weight, 4)
        else:
            f.score_contribution = 0.0


def resolve_path_override(
    file_path: Path | None,
    overrides: dict[str, PathOverride],
) -> PathOverride | None:
    """Return the most specific matching PathOverride for *file_path*.

    Specificity is determined by pattern length (longest match wins).
    Returns ``None`` when no pattern matches.
    """
    if file_path is None or not overrides:
        return None

    posix = file_path.as_posix()
    best: PathOverride | None = None
    best_len = -1
    for pattern, override in overrides.items():
        if fnmatch.fnmatch(posix, pattern) and len(pattern) > best_len:
            best = override
            best_len = len(pattern)
    return best


def apply_path_overrides(
    findings: list[Finding],
    overrides: dict[str, PathOverride],
    weights: SignalWeights,
) -> list[Finding]:
    """Filter findings and re-weight impacts based on per-path overrides.

    * Findings whose signal is listed in ``exclude_signals`` are removed.
    * Findings matched by an override with custom ``weights`` get their
      impact recomputed using those weights.

    Returns the (possibly reduced) list of findings.  Does **not** mutate
    the original list; instead returns a new one.
    """
    if not overrides:
        return findings

    kept: list[Finding] = []
    for f in findings:
        override = resolve_path_override(f.file_path, overrides)
        if override is None:
            kept.append(f)
            continue

        # Exclude signal?
        if f.signal_type in override.exclude_signals:
            continue

        # Re-weight if override provides custom weights
        if override.weights is not None:
            wd = override.weights.as_dict()
            key = _SIGNAL_WEIGHT_KEYS.get(f.signal_type, f.signal_type)
            w = wd.get(key, 0.1)
            breadth = min(_BREADTH_CAP, 1 + math.log(1 + len(f.related_files)))
            f.impact = round(w * f.score * breadth, 4)

        kept.append(f)

    return kept


def compute_signal_scores(
    findings: list[Finding],
    *,
    dampening_k: int = _DAMPENING_K,
    min_findings: int = 0,
) -> dict[str, float]:
    """Compute per-signal aggregate scores with count-dampened aggregation.

    Complexity: O(n) where n = total findings.

    Each signal's score = mean(finding_scores) * min(1, ln(1+n)/ln(1+k))
    where n = finding count and k = dampening constant.

    The logarithmic dampening prevents prolific low-confidence signals from
    dominating the composite score. A single high-score finding contributes
    less than many moderate findings — but the relationship is sublinear,
    not linear. This is calibrated via ablation study (see ADR-003).

    Args:
        dampening_k: count-dampening constant (default 10; small repos use 20).
        min_findings: per-signal minimum finding count to score (below → 0).
    """
    by_signal: dict[str, list[float]] = defaultdict(list)
    for f in findings:
        by_signal[f.signal_type].append(f.score)

    scores: dict[str, float] = {}
    # Iterate all known core signals plus any plugin signals in findings
    all_signal_ids = {str(sig) for sig in SignalType} | set(by_signal.keys())
    for sig in sorted(all_signal_ids):
        values = by_signal.get(sig, [])
        if values and len(values) >= max(1, min_findings):
            mean = sum(values) / len(values)
            dampening = min(1.0, math.log(1 + len(values)) / math.log(1 + dampening_k))
            scores[sig] = round(mean * dampening, 4)

    return scores


def composite_score(
    signal_scores: dict[str, float],
    weights: SignalWeights,
) -> float:
    """Compute weighted composite drift score."""
    weight_dict = weights.as_dict()
    total_weight = 0.0
    weighted_sum = 0.0

    for sig, score in signal_scores.items():
        key = _SIGNAL_WEIGHT_KEYS.get(sig, sig)
        w = weight_dict.get(key, 0.0)
        weighted_sum += score * w
        total_weight += w

    if total_weight < 0.001:
        return 0.0

    return round(min(1.0, weighted_sum / total_weight), 3)


# Grade bands: 0 = clean, 1 = maximum drift (inverted: A = best)
_GRADE_BANDS: tuple[tuple[float, str, str], ...] = (
    (0.20, "A", "Excellent"),
    (0.40, "B", "Good"),
    (0.60, "C", "Moderate Drift"),
    (0.80, "D", "Significant Drift"),
    (1.01, "F", "Critical Drift"),
)


def score_to_grade(score: float) -> tuple[str, str]:
    """Map a 0.0–1.0 drift score to a letter grade with description.

    Returns a ``(grade, label)`` tuple, e.g. ``("B", "Good")``.
    Lower scores are better — ``A`` means almost no drift.
    """
    for threshold, grade, label in _GRADE_BANDS:
        if score < threshold:
            return grade, label
    return "F", "Critical Drift"


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
    if fail_on == "none":
        return True

    threshold_map = {
        "critical": {Severity.CRITICAL},
        "high": {Severity.CRITICAL, Severity.HIGH},
        "medium": {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM},
        "low": {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW},
    }

    blocking = threshold_map.get(fail_on, {Severity.CRITICAL, Severity.HIGH})

    return all(f.severity not in blocking for f in findings)


def delta_gate_pass(
    current_score: float,
    history: Sequence[Mapping[str, object]],
    fail_on_delta: float,
    window: int = 5,
) -> bool:
    """Check if score degradation exceeds the delta threshold (ADR-005).

    Compares *current_score* against the mean of the last *window* snapshots.
    Returns ``True`` if the gate passes (degradation within budget).
    If no history exists, the gate always passes.
    """
    recent: list[float] = []
    for snapshot in history[-window:]:
        score = snapshot.get("drift_score")
        if isinstance(score, (int, float)):
            recent.append(float(score))
    if not recent:
        return True
    baseline = sum(recent) / len(recent)
    return (current_score - baseline) <= fail_on_delta


# ---------------------------------------------------------------------------
# Weight calibration from ablation data
# ---------------------------------------------------------------------------


def auto_calibrate_weights(
    findings: list[Finding],
    base_weights: SignalWeights,
    *,
    dominance_cap: float = 0.40,
) -> SignalWeights:
    """Runtime weight rebalancing based on finding distribution.

    Prevents any single signal from dominating the composite score by
    dampening signals that contribute a disproportionate share of findings.
    The base weight ranking is preserved — adjustment stays within a
    ±50 % band of each base weight.

    Used when ``auto_calibrate=True`` in config (the default).  This
    replaces manual re-calibration for most users while staying
    deterministic and reproducible (same findings → same weights).
    """
    if not findings:
        return base_weights

    weight_dict = base_weights.as_dict()

    # Count findings per weight key
    counts: dict[str, int] = defaultdict(int)
    for f in findings:
        key = _SIGNAL_WEIGHT_KEYS.get(f.signal_type, f.signal_type)
        counts[key] += 1

    total = sum(counts.values())
    if total == 0:
        return base_weights

    active_keys = sorted(k for k, v in weight_dict.items() if v > 0)

    adjustments: dict[str, float] = {}
    for key in active_keys:
        w = weight_dict[key]
        if w <= 0:
            continue
        share = counts.get(key, 0) / total
        if share > dominance_cap:
            # Dampen prolific signal — scale proportionally to excess
            excess = share - dominance_cap
            factor = max(0.5, 1.0 - excess)  # floor at 50 % of base
            adjustments[key] = w * factor
        elif counts.get(key, 0) == 0:
            # Signal produced nothing — keep base weight (no penalty)
            adjustments[key] = w
        else:
            adjustments[key] = w

    if not adjustments:
        return base_weights

    # Renormalize active weights so their sum matches the original active sum.
    # Keep key order canonical to make floating-point aggregation deterministic.
    original_active = math.fsum(weight_dict[k] for k in active_keys)
    new_active = math.fsum(adjustments[k] for k in active_keys)
    if new_active < 0.001:
        return base_weights

    scale = original_active / new_active

    scaled = {k: adjustments[k] * scale for k in active_keys}
    calibrated = {k: round(scaled[k], 4) for k in active_keys}

    # Correct rounding residue deterministically so active sum is stable.
    residual = round(original_active - math.fsum(calibrated[k] for k in active_keys), 4)
    if abs(residual) >= 0.0001:
        anchor = max(active_keys, key=lambda k: (scaled[k], k))
        corrected = round(calibrated[anchor] + residual, 4)
        if corrected <= 0:
            return base_weights
        calibrated[anchor] = corrected

    return base_weights.model_copy(update=calibrated)


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
