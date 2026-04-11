"""Per-repo signal calibration via statistical feedback integration (ADR-035).

This package provides Bayesian weight calibration based on three evidence
sources: explicit user feedback, git-outcome correlation, and GitHub
issue/PR label correlation.
"""

from drift.calibration.feedback import FeedbackEvent, load_feedback, record_feedback
from drift.calibration.profile_builder import build_profile

__all__ = [
    "FeedbackEvent",
    "build_profile",
    "load_feedback",
    "record_feedback",
]
