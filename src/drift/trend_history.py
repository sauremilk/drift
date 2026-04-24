"""Trend-context and history snapshot utilities (ADR-005)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from drift.models import RepoAnalysis, TrendContext
from drift.models._enums import TrendDirection
from drift.scoring.engine import compute_signal_scores

NOISE_FLOOR = 0.005
LOGGER = logging.getLogger(__name__)
_HISTORY_REPLACE_RETRIES = 5
_HISTORY_REPLACE_BACKOFF_SECONDS = 0.01


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


def _atomic_replace(tmp_path: Path, dest: Path) -> None:
    """Replace *dest* with *tmp_path*, retrying on Windows PermissionError."""
    for attempt in range(_HISTORY_REPLACE_RETRIES):
        try:
            tmp_path.replace(dest)
            return
        except PermissionError:
            if attempt >= _HISTORY_REPLACE_RETRIES - 1:
                raise
            time.sleep(_HISTORY_REPLACE_BACKOFF_SECONDS * (attempt + 1))


def save_history(history_file: Path, snapshots: list[dict]) -> None:
    """Persist snapshots (last 100) to the history JSON file."""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(snapshots[-100:], indent=2)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(history_file.parent),
        prefix=f".{history_file.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        _atomic_replace(tmp_path, history_file)
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
            direction=TrendDirection.BASELINE,
            recent_scores=[],
            history_depth=0,
            transition_ratio=0.0,
        )

    prev = valid[-1]["drift_score"]
    delta = round(current_score - prev, 4)

    if abs(delta) < NOISE_FLOOR:
        direction = TrendDirection.STABLE
    elif delta < 0:
        direction = TrendDirection.IMPROVING
    else:
        direction = TrendDirection.DEGRADING

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
    from drift.baseline import finding_fingerprint

    commit_hash = _resolve_head_commit_hash(repo_path)
    finding_fingerprints = sorted({finding_fingerprint(f) for f in analysis.findings})

    snapshots.append(
        {
            "timestamp": analysis.analyzed_at.isoformat(),
            "drift_score": analysis.drift_score,
            "signal_scores": {s: v for s, v in signal_scores.items()},
            "total_files": analysis.total_files,
            "total_findings": len(analysis.findings),
            "commit_hash": commit_hash,
            "finding_fingerprints": finding_fingerprints,
            "scope": scope,
        }
    )
    save_history(history_file, snapshots)
    return history_corrupt


def _resolve_head_commit_hash(repo_path: Path) -> str | None:
    """Return the current HEAD commit hash for the repository, if available."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return None

    commit_hash = completed.stdout.strip()
    return commit_hash or None
