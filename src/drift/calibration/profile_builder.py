"""Bayesian profile builder for per-repo signal weight calibration.

Aggregates evidence from multiple sources (user feedback, git correlation,
GitHub API) and computes calibrated signal weights using a Bayesian update
formula that gracefully degrades to defaults on insufficient data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from drift.calibration.feedback import FeedbackEvent, feedback_summary
from drift.config import SignalWeights

logger = logging.getLogger(__name__)


@dataclass
class SignalEvidence:
    """Aggregated evidence for a single signal."""

    signal_type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def total_observations(self) -> int:
        return self.tp + self.fp

    @property
    def precision(self) -> float:
        """Observed precision (TP / (TP + FP))."""
        n = self.total_observations
        if n == 0:
            return 1.0  # No evidence → assume default precision
        return self.tp / n

    @property
    def recall_indicator(self) -> float:
        """Rough recall indicator (TP / (TP + FN))."""
        denom = self.tp + self.fn
        if denom == 0:
            return 1.0
        return self.tp / denom


@dataclass
class CalibrationResult:
    """Result of a calibration run."""

    calibrated_weights: SignalWeights
    plugin_calibrated_weights: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, SignalEvidence] = field(default_factory=dict)
    confidence_per_signal: dict[str, float] = field(default_factory=dict)
    clamped_signals: list[str] = field(default_factory=list)
    total_events: int = 0
    signals_with_data: int = 0

    def weight_diff(self, default_weights: SignalWeights) -> dict[str, dict[str, float]]:
        """Compute the difference between calibrated and default weights.

        Returns::

            {
                "signal_name": {
                    "default": 0.16,
                    "calibrated": 0.12,
                    "delta": -0.04,
                    "confidence": 0.75
                },
                ...
            }
        """
        default_dict = default_weights.as_dict()
        calibrated_dict = self.calibrated_weights.as_dict()
        diff: dict[str, dict[str, float]] = {}
        for key in sorted(set(default_dict) | set(calibrated_dict)):
            d = default_dict.get(key, 0.0)
            c = calibrated_dict.get(key, 0.0)
            delta = round(c - d, 6)
            if abs(delta) > 0.0001:
                diff[key] = {
                    "default": d,
                    "calibrated": round(c, 6),
                    "delta": delta,
                    "confidence": self.confidence_per_signal.get(key, 0.0),
                }
        return diff


@dataclass
class CalibrationQualityAssessment:
    """Meta-quality view for calibrated weights vs defaults."""

    score: float
    magnitude: float
    min_confidence: float
    warning_count: int
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize quality metrics for CLI output and status persistence."""
        return {
            "score": self.score,
            "magnitude": self.magnitude,
            "min_confidence": self.min_confidence,
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
        }


def assess_calibration_quality(
    result: CalibrationResult,
    default_weights: SignalWeights,
    *,
    divergence_threshold: float = 0.8,
    low_confidence_threshold: float = 0.5,
    min_events_threshold: int = 10,
    magnitude_threshold: float = 0.8,
) -> CalibrationQualityAssessment:
    """Assess whether calibration changes appear trustworthy.

    The assessment compares calibrated vs default weights and combines change
    magnitude with the weakest supporting confidence. Large shifts with weak
    evidence are flagged as potential meta-drift.
    """
    diff = result.weight_diff(default_weights)
    if not diff:
        return CalibrationQualityAssessment(
            score=1.0,
            magnitude=0.0,
            min_confidence=1.0,
            warning_count=0,
            warnings=[],
        )

    relative_divergences: dict[str, float] = {}
    confidences: list[float] = []
    warnings: list[str] = []

    for signal_name, info in sorted(diff.items()):
        default_value = float(info.get("default", 0.0))
        calibrated_value = float(info.get("calibrated", default_value))
        confidence = float(info.get("confidence", 0.0))
        confidences.append(confidence)

        if abs(default_value) <= 1e-9:
            rel_divergence = abs(calibrated_value - default_value)
        else:
            rel_divergence = abs(calibrated_value - default_value) / abs(default_value)

        relative_divergences[signal_name] = rel_divergence
        if rel_divergence > divergence_threshold and confidence < low_confidence_threshold:
            warnings.append(
                "Signal "
                f"{signal_name} diverged by {rel_divergence:.1%} from default "
                f"with low confidence ({confidence:.1%})."
            )

    magnitude = sum(relative_divergences.values()) / max(1, len(relative_divergences))
    min_confidence = min(confidences) if confidences else 1.0

    if magnitude > magnitude_threshold and result.total_events < min_events_threshold:
        warnings.append(
            "Total calibration magnitude "
            f"{magnitude:.1%} exceeds threshold with only {result.total_events} events "
            f"(<{min_events_threshold})."
        )

    # High confidence should counterbalance larger shifts; low confidence should
    # reduce trust in aggressive recalibration.
    risk = min(1.0, magnitude) * (1.0 - min_confidence)
    score = round(max(0.0, 1.0 - risk), 4)

    return CalibrationQualityAssessment(
        score=score,
        magnitude=round(magnitude, 4),
        min_confidence=round(min_confidence, 4),
        warning_count=len(warnings),
        warnings=warnings,
    )


def build_profile(
    events: list[FeedbackEvent],
    default_weights: SignalWeights | None = None,
    *,
    min_samples: int = 20,
    fn_boost_factor: float = 0.1,
) -> CalibrationResult:
    """Build a calibrated signal profile from feedback evidence.

    Uses a Bayesian lerp between default weights and precision-scaled
    weights, gated by per-signal confidence (observation count / min_samples).

    Args:
        events: All feedback events from all sources.
        default_weights: Base weights to calibrate from. Uses SignalWeights()
            defaults if None.
        min_samples: Minimum TP+FP observations for full confidence.
        fn_boost_factor: How much to boost weight for signals with high FN
            rate (range 0.0-1.0).  0.0 disables FN boosting.

    Returns:
        CalibrationResult with calibrated weights and per-signal evidence.

    Notes:
        Plugin signals that appear in evidence but are not present in
        ``default_weights`` cannot be applied to ``calibrated_weights``
        directly. They are surfaced in
        ``CalibrationResult.plugin_calibrated_weights`` as derived calibration
        candidates and logged at debug level.
    """
    if default_weights is None:
        default_weights = SignalWeights()

    # Aggregate evidence
    summary = feedback_summary(events)
    evidence: dict[str, SignalEvidence] = {}
    for signal_type, counts in summary.items():
        evidence[signal_type] = SignalEvidence(
            signal_type=signal_type,
            tp=counts.get("tp", 0),
            fp=counts.get("fp", 0),
            fn=counts.get("fn", 0),
        )

    # Compute calibrated weights
    default_dict = default_weights.as_dict()

    # GitHub correlator can emit "_unattributed" FN when no prior signal was
    # linked to a buggy file. Distribute this weak FN evidence across active
    # signals so FN boosting can still react during calibration.
    unattributed_fn = evidence.get("_unattributed")
    if unattributed_fn is not None and unattributed_fn.fn > 0:
        for signal_key, default_w in default_dict.items():
            if default_w <= 0:
                continue
            signal_ev = evidence.get(signal_key)
            if signal_ev is None:
                evidence[signal_key] = SignalEvidence(signal_type=signal_key, fn=unattributed_fn.fn)
            else:
                signal_ev.fn += unattributed_fn.fn

    calibrated: dict[str, float] = {}
    plugin_calibrated: dict[str, float] = {}
    confidence_map: dict[str, float] = {}

    for signal_key, default_w in default_dict.items():
        ev = evidence.get(signal_key)
        if ev is None or ev.total_observations == 0:
            # No data → keep default
            calibrated[signal_key] = default_w
            confidence_map[signal_key] = 0.0
            continue

        # Confidence: ramps linearly from 0 to 1 as observations increase
        confidence = min(1.0, ev.total_observations / min_samples)
        confidence_map[signal_key] = round(confidence, 4)

        # Bayesian lerp: blend default with precision-scaled weight
        precision_scaled = default_w * ev.precision
        base_calibrated = (1.0 - confidence) * default_w + confidence * precision_scaled

        # Optional FN boost: if signal has many FN, slightly increase weight
        # (it fires too rarely — needs more prominence)
        if fn_boost_factor > 0 and ev.fn > 0:
            fn_ratio = ev.fn / (ev.tp + ev.fn) if (ev.tp + ev.fn) > 0 else 0.0
            fn_boost = default_w * fn_boost_factor * fn_ratio * confidence
            base_calibrated += fn_boost

        calibrated[signal_key] = round(base_calibrated, 6)

    plugin_signal_keys = sorted(
        signal_key
        for signal_key in evidence
        if signal_key not in default_dict and signal_key != "_unattributed"
    )
    if plugin_signal_keys:
        logger.debug(
            "Plugin calibration evidence found for signals not in configured weights: %s",
            ", ".join(plugin_signal_keys),
        )
    plugin_calibrated = {
        signal_key: 0.0
        for signal_key in plugin_signal_keys
        if evidence[signal_key].total_observations > 0
    }

    # Don't let any active signal go below a minimum threshold
    # (prevents total suppression from noisy feedback)
    min_floor = 0.001
    clamped_signals: list[str] = []
    for key, w in calibrated.items():
        if default_dict.get(key, 0.0) > 0 and w < min_floor:
            calibrated[key] = min_floor
            clamped_signals.append(key)
            logger.warning(
                "Signal %s calibrated to minimum floor (%s) - review feedback quality",
                key,
                min_floor,
            )

    calibrated_weights = default_weights.model_copy(update=calibrated)

    signals_with_data = sum(1 for e in evidence.values() if e.total_observations > 0)
    total_events = sum(c["tp"] + c["fp"] + c["fn"] for c in summary.values())

    return CalibrationResult(
        calibrated_weights=calibrated_weights,
        plugin_calibrated_weights=plugin_calibrated,
        evidence=evidence,
        confidence_per_signal=confidence_map,
        clamped_signals=sorted(clamped_signals),
        total_events=total_events,
        signals_with_data=signals_with_data,
    )
