"""Trajektorie-Klassifikation (ADR-088)."""

from __future__ import annotations

from drift.outcome_ledger._models import TrajectoryDirection

NOISE_FLOOR: float = 0.005


def classify_direction(delta: float) -> TrajectoryDirection:
    if delta < -NOISE_FLOOR:
        return TrajectoryDirection.IMPROVED
    if delta > NOISE_FLOOR:
        return TrajectoryDirection.REGRESSED
    return TrajectoryDirection.NEUTRAL


__all__ = ["NOISE_FLOOR", "classify_direction"]
