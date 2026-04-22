"""Markdown-Aggregat-Report fuer den Outcome-Ledger (ADR-088)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from statistics import fmean, pstdev

from drift.outcome_ledger._models import (
    STALENESS_HISTORICAL_DAYS,
    STALENESS_WARNING_DAYS,
    AuthorType,
    MergeTrajectory,
    TrajectoryDirection,
)


def render_markdown_report(trajectories: Sequence[MergeTrajectory]) -> str:
    if not trajectories:
        return (
            "# Outcome Trajectory Report\n\n"
            "_No merges available for retrospective analysis._\n"
        )

    fresh: list[MergeTrajectory] = []
    historical: list[MergeTrajectory] = []
    warning: list[MergeTrajectory] = []
    for t in trajectories:
        if t.staleness_days > STALENESS_HISTORICAL_DAYS:
            historical.append(t)
        elif t.staleness_days > STALENESS_WARNING_DAYS:
            warning.append(t)
        else:
            fresh.append(t)

    lines: list[str] = ["# Outcome Trajectory Report", ""]
    lines.append(f"- merges analysed: **{len(trajectories)}**")
    lines.append(f"- fresh: {len(fresh)}")
    lines.append(f"- staleness-warning: {len(warning)}")
    lines.append(f"- historical: {len(historical)}")
    lines.append("")

    lines.extend(_render_direction_table(trajectories))
    lines.append("")
    lines.extend(_render_author_split(trajectories))
    lines.append("")
    lines.extend(_render_per_signal(trajectories))

    if warning:
        lines.append("")
        lines.append(f"## Staleness warnings (>{STALENESS_WARNING_DAYS}d)")
        for t in warning:
            lines.append(f"- {t.merge_commit} - {t.staleness_days}d old")

    if historical:
        lines.append("")
        lines.append(f"## Historical records (>{STALENESS_HISTORICAL_DAYS}d)")
        for t in historical:
            lines.append(f"- {t.merge_commit} - {t.staleness_days}d old")

    return "\n".join(lines) + "\n"


def _render_direction_table(trajectories: Iterable[MergeTrajectory]) -> list[str]:
    counts: dict[TrajectoryDirection, int] = defaultdict(int)
    for t in trajectories:
        counts[t.direction] += 1

    out = ["## Trajectory direction", "", "| direction | count |", "|---|---|"]
    for direction in TrajectoryDirection:
        out.append(f"| {direction.value} | {counts.get(direction, 0)} |")
    return out


def _render_author_split(trajectories: Iterable[MergeTrajectory]) -> list[str]:
    buckets: dict[AuthorType, list[float]] = defaultdict(list)
    for t in trajectories:
        buckets[t.author_type].append(t.delta)

    out = [
        "## Author-type split",
        "",
        "| author_type | n | mean | stdev |",
        "|---|---|---|---|",
    ]
    for author in AuthorType:
        deltas = buckets.get(author, [])
        n = len(deltas)
        if n == 0:
            out.append(f"| {author.value} | 0 | - | - |")
            continue
        mean = fmean(deltas)
        stdev = pstdev(deltas) if n > 1 else 0.0
        out.append(f"| {author.value} | {n} | {mean:+.4f} | {stdev:.4f} |")
    return out


def _render_per_signal(trajectories: Iterable[MergeTrajectory]) -> list[str]:
    per_signal: dict[str, list[float]] = defaultdict(list)
    for t in trajectories:
        for signal, delta in t.per_signal_delta.items():
            per_signal[signal].append(delta)

    if not per_signal:
        return ["## Per-signal aggregate", "", "_No per-signal deltas recorded._"]

    out = [
        "## Per-signal aggregate",
        "",
        "| signal | n | mean | stdev |",
        "|---|---|---|---|",
    ]
    for signal in sorted(per_signal):
        deltas = per_signal[signal]
        n = len(deltas)
        mean = fmean(deltas)
        stdev = pstdev(deltas) if n > 1 else 0.0
        out.append(f"| {signal} | {n} | {mean:+.4f} | {stdev:.4f} |")
    return out


__all__ = ["render_markdown_report"]
