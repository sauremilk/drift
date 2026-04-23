"""Deterministic reward chain for recommendation quality assessment.

Computes a composite ``RewardScore`` for each recommendation based on
four sub-scores — without any LLM call or network request (F-10).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from drift.models import Finding
from drift.outcome_tracker import Outcome
from drift.recommendations import Recommendation

# Sub-score weights (F-08)
_W_FIX_SPEED = 0.4
_W_SPECIFICITY = 0.3
_W_EFFORT_ACCURACY = 0.2
_W_NO_REGRESSION = 0.1

# Verbs considered "generic" in recommendation descriptions
_GENERIC_VERBS = re.compile(
    r"\b(consider|review|ensure|evaluate|assess|investigate|examine|verify|check)\b",
    re.IGNORECASE,
)

# Effort label → numeric class for accuracy comparison
_EFFORT_CLASS: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


@dataclass
class RewardScore:
    """Quality score for a single recommendation."""

    total: float  # 0.0–1.0
    breakdown: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0


def _score_fix_speed(outcome: Outcome | None) -> float:
    """0.0–1.0: fast fixes score high, slow or unknown low."""
    if outcome is None or outcome.days_to_fix is None:
        return 0.0
    days = outcome.days_to_fix
    if days <= 1.0:
        return 1.0
    if days >= 14.0:
        return 0.0
    # Linear decay from 1.0 at day 1 to 0.0 at day 14
    return max(0.0, 1.0 - (days - 1.0) / 13.0)


def _score_specificity(recommendation: Recommendation, finding: Finding) -> float:
    """0.0–1.0: concrete, actionable text scores higher."""
    desc = recommendation.description
    score = 0.5  # baseline

    # Bonus: contains a concrete file path
    if finding.file_path and finding.file_path.name in desc:
        score += 0.2

    # Bonus: contains a concrete symbol name
    symbol = finding.symbol
    if not symbol and finding.logical_location:
        symbol = finding.logical_location.name
    if symbol and symbol in desc:
        score += 0.2

    # Penalty: heavy use of generic verbs
    generic_count = len(_GENERIC_VERBS.findall(desc))
    word_count = max(len(desc.split()), 1)
    generic_ratio = generic_count / word_count
    if generic_ratio > 0.05:
        score -= 0.2

    return max(0.0, min(1.0, score))


def _score_effort_accuracy(
    outcome: Outcome | None,
    calibrated_effort: str | None = None,
) -> float:
    """0.0–1.0: how well the effort label matched actual fix duration.

    When *calibrated_effort* is provided (the statistically-derived label from
    ``recommendation_calibrator.py``), it is used as the expected class instead
    of the raw ``outcome.effort_estimate``.
    """
    if outcome is None or outcome.days_to_fix is None:
        return 0.0

    days = outcome.days_to_fix
    if days <= 1.0:
        actual_class = 0  # low
    elif days <= 5.0:
        actual_class = 1  # medium
    else:
        actual_class = 2  # high

    estimated_label = (
        calibrated_effort if calibrated_effort is not None else outcome.effort_estimate
    )
    estimated_class = _EFFORT_CLASS.get(estimated_label, 1)
    diff = abs(actual_class - estimated_class)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    return 0.0


def _score_no_regression(
    outcome: Outcome | None,
    all_outcomes: list[Outcome] | None = None,
) -> float:
    """1.0 if the finding did not reappear within 30 days of resolution."""
    if outcome is None or outcome.resolved_at is None:
        return 0.0

    if all_outcomes is None:
        # No data to check regression — optimistic default
        return 1.0

    from datetime import datetime

    resolved_dt = datetime.fromisoformat(outcome.resolved_at)

    for other in all_outcomes:
        if other.fingerprint != outcome.fingerprint:
            continue
        if other is outcome:
            continue
        reported_dt = datetime.fromisoformat(other.reported_at)
        delta = (reported_dt - resolved_dt).total_seconds() / 86400.0
        if 0 < delta <= 30:
            return 0.0  # regression detected

    return 1.0


def compute_reward(
    outcome: Outcome | None,
    recommendation: Recommendation,
    finding: Finding,
    *,
    all_outcomes: list[Outcome] | None = None,
    calibrated_effort: str | None = None,
) -> RewardScore:
    """Compute a deterministic reward score for a recommendation.

    Parameters
    ----------
    outcome:
        The outcome for this finding, or ``None`` if the finding
        has not yet been resolved.
    recommendation:
        The recommendation that was generated.
    finding:
        The original finding the recommendation is for.
    all_outcomes:
        Full outcome history, used for regression detection.
    calibrated_effort:
        Statistically-calibrated effort label for this signal type (from
        ``recommendation_calibrator.load_effort``).  When provided, replaces
        ``outcome.effort_estimate`` in the effort-accuracy sub-score.

    Returns
    -------
    RewardScore
        Composite score with sub-score breakdown and confidence.
    """
    fix_speed = _score_fix_speed(outcome)
    specificity = _score_specificity(recommendation, finding)
    effort_accuracy = _score_effort_accuracy(outcome, calibrated_effort)
    no_regression = _score_no_regression(outcome, all_outcomes)

    breakdown = {
        "fix_speed": round(fix_speed, 4),
        "specificity": round(specificity, 4),
        "effort_accuracy": round(effort_accuracy, 4),
        "no_regression": round(no_regression, 4),
    }

    raw_total = (
        _W_FIX_SPEED * fix_speed
        + _W_SPECIFICITY * specificity
        + _W_EFFORT_ACCURACY * effort_accuracy
        + _W_NO_REGRESSION * no_regression
    )

    # Confidence: < 0.5 when no outcome data (F-09)
    if outcome is None:
        confidence = 0.3
    elif outcome.resolved_at is None:
        confidence = 0.4
    else:
        confidence = min(1.0, 0.6 + 0.4 * min(fix_speed, 1.0))

    total = round(raw_total * confidence, 4)

    return RewardScore(
        total=total,
        breakdown=breakdown,
        confidence=round(confidence, 4),
    )


# ---------------------------------------------------------------------------
# Reward log persistence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RewardLogEntry:
    """Single row written to .drift/reward_log.jsonl."""

    ts: str
    signal_type: str
    finding_id: str
    total: float
    breakdown: dict
    confidence: float
    recommendation_id: str | None = None


def append_reward_log(path: Path, entry: RewardLogEntry) -> None:
    """Append *entry* as one JSON line to *path*, creating it if absent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": entry.ts,
        "signal_type": entry.signal_type,
        "finding_id": entry.finding_id,
        "recommendation_id": entry.recommendation_id,
        "total": entry.total,
        "breakdown": entry.breakdown,
        "confidence": entry.confidence,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
