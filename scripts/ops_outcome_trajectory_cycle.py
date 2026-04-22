"""Retrospective outcome-trajectory runner (ADR-088 / K2 MVP).

Usage:
    python scripts/ops_outcome_trajectory_cycle.py --repo . --limit 20

Writes a JSON + Markdown report under ``.drift/reports/<ts>/`` and - when
``--apply`` is set - appends trajectory records to
``.drift/outcome_ledger.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from drift.api.analyze_commit_pair import analyze_commit_pair
from drift.outcome_ledger import (
    AuthorType,
    MergeTrajectory,
    append_trajectory,
    render_markdown_report,
)
from drift.outcome_ledger.correlator import classify_direction
from drift.outcome_ledger.walker import MergeCandidate, walk_recent_merges


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrospective outcome-trajectory runner")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--since-days", type=int, default=180)
    parser.add_argument(
        "--include-ai-only",
        action="store_true",
        help="Restrict analysis to AI-authored merges only.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Append trajectories to .drift/outcome_ledger.jsonl (default is dry-run).",
    )
    return parser.parse_args(argv)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def _staleness_days(timestamp: str, now: datetime) -> int:
    try:
        when = datetime.fromisoformat(timestamp)
    except ValueError:
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta = now - when
    return max(int(delta.days), 0)


def _per_signal_delta(
    pre_findings: object, post_findings: object
) -> dict[str, float]:
    pre_counts: dict[str, int] = {}
    post_counts: dict[str, int] = {}
    for finding in getattr(pre_findings, "findings", []) or []:
        signal = getattr(finding, "signal_type", None) or getattr(finding, "signal", None)
        if signal is None:
            continue
        pre_counts[str(signal)] = pre_counts.get(str(signal), 0) + 1
    for finding in getattr(post_findings, "findings", []) or []:
        signal = getattr(finding, "signal_type", None) or getattr(finding, "signal", None)
        if signal is None:
            continue
        post_counts[str(signal)] = post_counts.get(str(signal), 0) + 1

    signals = set(pre_counts) | set(post_counts)
    return {
        signal: float(post_counts.get(signal, 0) - pre_counts.get(signal, 0))
        for signal in sorted(signals)
    }


def _build_trajectory(
    repo_path: Path,
    candidate: MergeCandidate,
    now: datetime,
) -> MergeTrajectory | None:
    try:
        pre, post = analyze_commit_pair(
            repo_path, candidate.parent_sha, candidate.merge_sha
        )
    except subprocess.CalledProcessError:
        return None

    pre_score = float(getattr(pre, "drift_score", 0.0) or 0.0)
    post_score = float(getattr(post, "drift_score", 0.0) or 0.0)
    delta = post_score - pre_score

    return MergeTrajectory(
        merge_commit=candidate.merge_sha,
        parent_commit=candidate.parent_sha,
        timestamp=candidate.timestamp,
        author_type=candidate.author_type,
        ai_attribution_confidence=candidate.ai_confidence,
        pre_score=pre_score,
        post_score=post_score,
        delta=delta,
        direction=classify_direction(delta),
        per_signal_delta=_per_signal_delta(pre, post),
        recommendation_outcomes=(),
        staleness_days=_staleness_days(candidate.timestamp, now),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    repo_path = args.repo.resolve()
    now = datetime.now(UTC)

    candidates = walk_recent_merges(
        repo_path, limit=args.limit, since_days=args.since_days
    )

    if args.include_ai_only:
        candidates = [c for c in candidates if c.author_type == AuthorType.AI]

    trajectories: list[MergeTrajectory] = []
    for candidate in candidates:
        trajectory = _build_trajectory(repo_path, candidate, now)
        if trajectory is not None:
            trajectories.append(trajectory)

    ts = now.strftime("%Y%m%dT%H%M%SZ")
    report_dir = repo_path / ".drift" / "reports" / ts
    report_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "outcome_trajectory.json").write_text(
        json.dumps(
            [t.model_dump(mode="json") for t in trajectories], indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    (report_dir / "outcome_trajectory.md").write_text(
        render_markdown_report(trajectories), encoding="utf-8"
    )

    if args.apply:
        ledger_path = repo_path / ".drift" / "outcome_ledger.jsonl"
        for trajectory in trajectories:
            append_trajectory(ledger_path, trajectory)
        print(f"Appended {len(trajectories)} trajectories to {ledger_path}")
    else:
        print(
            f"Dry-run: report written to {report_dir} "
            f"({len(trajectories)} trajectories). Pass --apply to persist."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
