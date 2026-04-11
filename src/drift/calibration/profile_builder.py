"""Bayesian profile builder for per-repo signal weight calibration.

Aggregates evidence from multiple sources (user feedback, git correlation,
GitHub API) and computes calibrated signal weights using a Bayesian update
formula that gracefully degrades to defaults on insufficient data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from drift.calibration.feedback import FeedbackEvent, feedback_summary
from drift.config import SignalWeights


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
    evidence: dict[str, SignalEvidence] = field(default_factory=dict)
    confidence_per_signal: dict[str, float] = field(default_factory=dict)
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
    calibrated: dict[str, float] = {}
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

    # Don't let any active signal go below a minimum threshold
    # (prevents total suppression from noisy feedback)
    for key, w in calibrated.items():
        if default_dict.get(key, 0.0) > 0 and w < 0.001:
            calibrated[key] = 0.001

    calibrated_weights = default_weights.model_copy(update=calibrated)

    signals_with_data = sum(1 for e in evidence.values() if e.total_observations > 0)

    return CalibrationResult(
        calibrated_weights=calibrated_weights,
        evidence=evidence,
        confidence_per_signal=confidence_map,
        total_events=len(events),
        signals_with_data=signals_with_data,
    )
