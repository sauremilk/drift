"""Quality-drift detection between analysis runs.

Compares two run snapshots and classifies the trajectory
as *improving*, *stable*, or *degrading*, with an actionable advisory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Minimal snapshot of a single analysis run.

    Attributes:
        score: Composite drift score (0–100, lower is better).
        finding_count: Total number of findings.
        tool_calls: Number of tool calls at time of snapshot.
    """

    score: float
    finding_count: int
    tool_calls: int = 0


@dataclass(frozen=True, slots=True)
class QualityDrift:
    """Result of comparing two run snapshots.

    Attributes:
        direction: ``improving``, ``stable``, or ``degrading``.
        score_delta: Change in score (negative = improving).
        finding_delta: Change in finding count (negative = improving).
        advisory: Human-readable guidance for the agent.
    """

    direction: str  # "improving" | "stable" | "degrading"
    score_delta: float
    finding_delta: int
    advisory: str


# Thresholds below which changes are considered noise.
_SCORE_TOLERANCE = 0.5
_FINDING_TOLERANCE = 0


def compare_runs(before: RunSnapshot, after: RunSnapshot) -> QualityDrift:
    """Compare two run snapshots and return a quality-drift assessment."""
    score_delta = round(after.score - before.score, 2)
    finding_delta = after.finding_count - before.finding_count

    # Classify direction
    if score_delta < -_SCORE_TOLERANCE or finding_delta < -_FINDING_TOLERANCE:
        direction = "improving"
    elif score_delta > _SCORE_TOLERANCE or finding_delta > _FINDING_TOLERANCE:
        direction = "degrading"
    else:
        direction = "stable"

    advisory = _build_advisory(direction, score_delta, finding_delta, after.tool_calls)

    return QualityDrift(
        direction=direction,
        score_delta=score_delta,
        finding_delta=finding_delta,
        advisory=advisory,
    )


def _build_advisory(
    direction: str, score_delta: float, finding_delta: int, tool_calls: int
) -> str:
    if direction == "improving":
        return (
            f"Score improved by {abs(score_delta):.1f} points, "
            f"{abs(finding_delta)} fewer findings. Keep going."
        )
    if direction == "degrading":
        return (
            f"Score worsened by {score_delta:.1f} points, "
            f"{finding_delta} more findings. "
            "Consider reverting recent changes or running drift_explain."
        )
    return "Score and findings stable. Proceed with next task."


def quality_drift_from_history(
    run_history: list[dict[str, Any]],
) -> QualityDrift | None:
    """Compare the last two entries in a run history list.

    Returns ``None`` if fewer than two snapshots exist.
    """
    if len(run_history) < 2:
        return None
    prev = run_history[-2]
    curr = run_history[-1]
    return compare_runs(
        RunSnapshot(
            score=prev["score"],
            finding_count=prev["finding_count"],
            tool_calls=prev.get("tool_calls_at", 0),
        ),
        RunSnapshot(
            score=curr["score"],
            finding_count=curr["finding_count"],
            tool_calls=curr.get("tool_calls_at", 0),
        ),
    )
