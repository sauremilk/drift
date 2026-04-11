"""Threshold adapter for signal-specific score threshold adjustment.

Prepares infrastructure for adaptive threshold calibration based on
accumulated feedback metrics.  **Disabled by default** — activation
requires ``calibration.threshold_adaptation_enabled: true`` in the
drift config.

This module is intentionally kept behind a feature gate because the
calibration moratorium is still active.  It provides pure computation
with no I/O so that it can be tested deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from drift.calibration.feedback import SignalFeedbackMetrics


@dataclass(frozen=True)
class AdaptedThreshold:
    """Result of a threshold adaptation computation."""

    signal_type: str
    base_threshold: float
    adapted_threshold: float
    adjustment: float
    clamped: bool


def adapt_threshold(
    signal_type: str,
    base_threshold: float,
    metrics: SignalFeedbackMetrics | None,
    *,
    enabled: bool = False,
    min_threshold: float = 0.1,
    max_threshold: float = 0.95,
    fp_sensitivity: float = 0.3,
    fn_sensitivity: float = 0.2,
    min_observations: int = 5,
) -> AdaptedThreshold:
    """Compute an adapted threshold for a signal based on feedback metrics.

    When *enabled* is ``False`` (default), the base threshold is returned
    unchanged.  When enabled:

    * **High FP rate** → threshold moves *up* (more restrictive).
    * **High FN rate** → threshold moves *down* (more permissive).

    The adjustment magnitude is controlled by *fp_sensitivity* and
    *fn_sensitivity* and is clamped to [*min_threshold*, *max_threshold*].

    Args:
        signal_type: Signal identifier (informational, stored in result).
        base_threshold: The default threshold before adaptation.
        metrics: Aggregated feedback metrics for this signal.  ``None``
            is treated the same as zero observations.
        enabled: Feature gate — ``False`` returns base unchanged.
        min_threshold: Hard lower bound for the adapted value.
        max_threshold: Hard upper bound for the adapted value.
        fp_sensitivity: Scale factor for FP-driven upward adjustment
            (0.0–1.0).
        fn_sensitivity: Scale factor for FN-driven downward adjustment
            (0.0–1.0).
        min_observations: Minimum TP+FP observations before any
            adjustment is applied.

    Returns:
        :class:`AdaptedThreshold` with the (possibly unchanged) result.
    """
    if not enabled or metrics is None or metrics.total_observations < min_observations:
        return AdaptedThreshold(
            signal_type=signal_type,
            base_threshold=base_threshold,
            adapted_threshold=base_threshold,
            adjustment=0.0,
            clamped=False,
        )

    # FP-driven: raise threshold proportional to false-positive rate
    fp_rate = metrics.fp / metrics.total_observations if metrics.total_observations else 0.0
    fp_adj = fp_rate * fp_sensitivity

    # FN-driven: lower threshold proportional to false-negative rate
    fn_denom = metrics.tp + metrics.fn
    fn_rate = metrics.fn / fn_denom if fn_denom else 0.0
    fn_adj = fn_rate * fn_sensitivity

    raw = base_threshold + fp_adj - fn_adj
    clamped = raw < min_threshold or raw > max_threshold
    adapted = max(min_threshold, min(max_threshold, raw))

    return AdaptedThreshold(
        signal_type=signal_type,
        base_threshold=base_threshold,
        adapted_threshold=round(adapted, 6),
        adjustment=round(adapted - base_threshold, 6),
        clamped=clamped,
    )
