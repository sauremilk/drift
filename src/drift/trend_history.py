"""Trend-context and history snapshot utilities (ADR-005)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from drift.models import RepoAnalysis, TrendContext
from drift.scoring.engine import compute_signal_scores

NOISE_FLOOR = 0.005
LOGGER = logging.getLogger(__name__)


def load_history_with_status(history_file: Path) -> tuple[list[dict], bool]:
    """Load snapshots and indicate whether the history file was corrupt."""
    if not history_file.exists():
        return [], False
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data, False
        LOGGER.warning(
            "Trend history file %s is corrupt: expected JSON list but got %s; history will reset.",
            history_file,
            type(data).__name__,
        )
        return [], True
    except Exception as exc:
        LOGGER.warning(
            "Trend history file %s is corrupt and cannot be parsed; history will reset.",
            history_file,
            exc_info=exc,
        )
        return [], True


def load_history(history_file: Path) -> list[dict]:
    """Load snapshots from the history JSON file."""
    snapshots, _is_corrupt = load_history_with_status(history_file)
    return snapshots


def save_history(history_file: Path, snapshots: list[dict]) -> None:
    """Persist snapshots with independent per-scope retention.

    Keeps up to the last 100 snapshots per scope ("repo" and "diff") so
    high-volume diff runs cannot evict repo-scoped history (Issue #440).
    """
    history_file.parent.mkdir(parents=True, exist_ok=True)
    remaining = {"repo": 100, "diff": 100}
    retained_reversed: list[dict] = []
    for snapshot in reversed(snapshots):
        scope = snapshot_scope(snapshot)
        if remaining[scope] <= 0:
            continue
        retained_reversed.append(snapshot)
        remaining[scope] -= 1

    retained = list(reversed(retained_reversed))
    content = json.dumps(retained, indent=2)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(history_file.parent),
        prefix=f".{history_file.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp_path.replace(history_file)
    except OSError:
        with suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


def build_trend_context(current_score: float, snapshots: list[dict]) -> TrendContext:
    """Compute trend context from history snapshots."""
    # Filter to entries that have a numeric drift_score — malformed entries
    # (missing key, wrong type) are silently skipped so a single corrupt
    # history entry does not crash the entire analysis pipeline.
    valid = [
        s for s in snapshots
        if isinstance(s.get("drift_score"), (int, float))
    ]

    if not valid:
        return TrendContext(
            previous_score=None,
            delta=None,
            direction="baseline",
            recent_scores=[],
            history_depth=0,
            transition_ratio=0.0,
        )

    prev = valid[-1]["drift_score"]
    delta = round(current_score - prev, 4)

    if abs(delta) < NOISE_FLOOR:
        direction = "stable"
    elif delta < 0:
        direction = "improving"
    else:
        direction = "degrading"

    recent = [s["drift_score"] for s in valid[-5:]]

    return TrendContext(
        previous_score=prev,
        delta=delta,
        direction=direction,
        recent_scores=recent,
        history_depth=len(valid),
        transition_ratio=0.0,
    )


def snapshot_scope(snapshot: dict) -> str:
    """Resolve snapshot scope, keeping legacy entries backward-compatible."""
    scope = snapshot.get("scope")
    if scope == "diff":
        return "diff"
    return "repo"


def apply_trend_and_persist_snapshot(
    repo_path: Path,
    cache_dir: str,
    analysis: RepoAnalysis,
    *,
    scope: str,
) -> bool:
    """Attach trend context and persist a scoped history snapshot.

    Returns True if history content was corrupt and had to be treated as empty.
    """
    history_file = repo_path / cache_dir / "history.json"
    snapshots, history_corrupt = load_history_with_status(history_file)

    scoped_history = [s for s in snapshots if snapshot_scope(s) == scope]
    analysis.trend = build_trend_context(analysis.drift_score, scoped_history)

    if analysis.trend and analysis.findings:
        analysis.trend.transition_ratio = round(
            analysis.context_tagged_count / len(analysis.findings),
            3,
        )

    signal_scores = compute_signal_scores(analysis.findings)
    snapshots.append(
        {
            "timestamp": analysis.analyzed_at.isoformat(),
            "drift_score": analysis.drift_score,
            "signal_scores": {s: v for s, v in signal_scores.items()},
            "total_files": analysis.total_files,
            "total_findings": len(analysis.findings),
            "scope": scope,
        }
    )
    save_history(history_file, snapshots)
    return history_corrupt
