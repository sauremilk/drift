"""Scoring engine for Drift."""

from drift.scoring.engine import (
    composite_score,
    compute_module_scores,
    compute_signal_scores,
    severity_gate_pass,
)

__all__ = [
    "composite_score",
    "compute_module_scores",
    "compute_signal_scores",
    "severity_gate_pass",
]
