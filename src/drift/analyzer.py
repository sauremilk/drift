"""Main analysis orchestrator - coordinates high-level pipeline entry points."""

from __future__ import annotations

import datetime
import importlib
import logging
import pkgutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import drift.signals
from drift.config import DriftConfig
from drift.ingestion.file_discovery import discover_files
from drift.models import FileInfo, RepoAnalysis, TrendContext
from drift.models._enums import AnalysisStatus
from drift.pipeline import (
    DEFAULT_WORKERS,
    AnalysisPipeline,
    SignalPhase,
    fetch_git_history,
    is_git_repo,
    make_degradation_event,
    resolve_worker_count,
)
from drift.signals.base import create_signals
from drift.trend_history import (
    NOISE_FLOOR,
)
from drift.trend_history import (
    apply_trend_and_persist_snapshot as trend_apply_and_persist,
)
from drift.trend_history import (
    build_trend_context as trend_build_context,
)
from drift.trend_history import (
    load_history as trend_load_history,
)
from drift.trend_history import (
    load_history_with_status as trend_load_history_with_status,
)
from drift.trend_history import (
    save_history as trend_save_history,
)
from drift.trend_history import (
    snapshot_scope as trend_snapshot_scope,
)

# Auto-discover all signal modules so @register_signal decorators execute.
for _finder, _mod_name, _ispkg in pkgutil.iter_modules(drift.signals.__path__):
    importlib.import_module(f"drift.signals.{_mod_name}")

ProgressCallback = Callable[[str, int, int], None]
_DEFAULT_WORKERS = DEFAULT_WORKERS


def _is_git_repo(path: Path) -> bool:
    """Check whether *path* is inside a git working tree."""
    return is_git_repo(path)


def _fetch_git_history(
    repo_path: Path,
    since_days: int,
    known_files: set[str],
    ai_confidence_threshold: float = 0.50,
) -> tuple[list, dict]:
    """Run git history parsing (designed to run in a background thread)."""
    return fetch_git_history(repo_path, since_days, known_files, ai_confidence_threshold)


def _make_degradation_event(
    *,
    cause: str,
    component: str,
    message: str,
    details: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a machine-readable degradation event payload."""
    return make_degradation_event(
        cause=cause,
        component=component,
        message=message,
        details=details,
    )


def _mark_analysis_degraded(
    analysis: RepoAnalysis,
    *,
    cause: str,
    component: str,
    message: str,
    details: dict[str, str] | None = None,
) -> None:
    """Attach a degradation event to an existing analysis result."""
    analysis.analysis_status = AnalysisStatus.DEGRADED
    if cause not in analysis.degradation_causes:
        analysis.degradation_causes.append(cause)
    if component not in analysis.degradation_components:
        analysis.degradation_components.append(component)
    analysis.degradation_events.append(
        _make_degradation_event(
            cause=cause,
            component=component,
            message=message,
            details=details,
        )
    )


def _run_pipeline(
    repo_path: Path,
    files: list[FileInfo],
    config: DriftConfig,
    since_days: int = 90,
    on_progress: ProgressCallback | None = None,
    workers: int = _DEFAULT_WORKERS,
    active_signals: set[str] | None = None,
    discover_duration_seconds: float = 0.0,
) -> RepoAnalysis:
    """Shared analysis pipeline delegated to composable phase components."""
    pipeline = AnalysisPipeline(signal_phase=SignalPhase(signal_factory=create_signals))
    return pipeline.run(
        repo_path,
        files,
        config,
        since_days=since_days,
        on_progress=on_progress,
        workers=workers,
        active_signals=active_signals,
        discover_duration_seconds=discover_duration_seconds,
    )


# ---------------------------------------------------------------------------
# Trend context compatibility wrappers (ADR-005)
# ---------------------------------------------------------------------------

_NOISE_FLOOR = NOISE_FLOOR


def _load_history(history_file: Path) -> list[dict]:
    """Load snapshots from the history JSON file."""
    return trend_load_history(history_file)


def _load_history_with_status(history_file: Path) -> tuple[list[dict], bool]:
    """Load snapshots and indicate whether the history file was corrupt."""
    return trend_load_history_with_status(history_file)


def _save_history(history_file: Path, snapshots: list[dict]) -> None:
    """Persist snapshots (last 100) to the history JSON file."""
    trend_save_history(history_file, snapshots)


def _build_trend_context(current_score: float, snapshots: list[dict]) -> TrendContext:
    """Compute trend context from history snapshots."""
    return trend_build_context(current_score, snapshots)


def _snapshot_scope(snapshot: dict) -> str:
    """Resolve snapshot scope, keeping legacy entries backward-compatible."""
    return trend_snapshot_scope(snapshot)


def _apply_trend_and_persist_snapshot(
    repo_path: Path,
    config: DriftConfig,
    analysis: RepoAnalysis,
    *,
    scope: str,
) -> None:
    """Attach trend context and persist a scoped history snapshot."""
    history_corrupt = trend_apply_and_persist(
        repo_path,
        config.cache_dir,
        analysis,
        scope=scope,
    )
    if history_corrupt:
        _mark_analysis_degraded(
            analysis,
            cause="history_cache_corrupt",
            component="history_cache",
            message="History cache could not be parsed; trend baseline restarted.",
            details={"file": (repo_path / config.cache_dir / "history.json").as_posix()},
        )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def analyze_repo(
    repo_path: Path,
    config: DriftConfig | None = None,
    since_days: int = 90,
    target_path: str | None = None,
    on_progress: ProgressCallback | None = None,
    workers: int | None = None,
    active_signals: set[str] | None = None,
) -> RepoAnalysis:
    """Run full drift analysis on a repository."""
    repo_path = repo_path.resolve()
    start = time.monotonic()
    if config is None:
        config = DriftConfig.load(repo_path)

    if on_progress:
        on_progress("Discovering files", 0, 0)

    skipped_langs: dict[str, int] = {}
    discover_started_at = time.monotonic()
    files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
        max_files=config.thresholds.max_discovery_files,
        skipped_out=skipped_langs,
        ts_enabled=config.languages.typescript,
        cache_dir=config.cache_dir,
    )

    if target_path:
        target = Path(target_path).as_posix().strip("/")
        if target:
            files = [
                f
                for f in files
                if (
                    f.path.as_posix().strip("/") == target
                    or f.path.as_posix().strip("/").startswith(target + "/")
                )
            ]
    discover_duration_seconds = round(
        max(0.0, time.monotonic() - discover_started_at),
        3,
    )

    effective_workers = resolve_worker_count(
        config=config,
        files=files,
        requested_workers=workers,
    )

    analysis = _run_pipeline(
        repo_path,
        files,
        config,
        since_days=since_days,
        on_progress=on_progress,
        workers=effective_workers,
        active_signals=active_signals,
        discover_duration_seconds=discover_duration_seconds,
    )
    analysis.analysis_duration_seconds = round(time.monotonic() - start, 2)
    analysis.phase_timings["discover_seconds"] = discover_duration_seconds
    analysis.phase_timings["total_seconds"] = analysis.analysis_duration_seconds
    analysis.skipped_files = sum(skipped_langs.values())
    analysis.skipped_languages = skipped_langs

    _apply_trend_and_persist_snapshot(
        repo_path,
        config,
        analysis,
        scope="repo",
    )

    return analysis


def analyze_diff(
    repo_path: Path,
    config: DriftConfig | None = None,
    diff_ref: str = "HEAD~1",
    diff_mode: str = "ref",
    workers: int | None = None,
    on_progress: ProgressCallback | None = None,
    since_days: int = 90,
    target_path: str | None = None,
) -> RepoAnalysis:
    """Analyze only files changed since a given git ref."""
    logger = logging.getLogger("drift")
    repo_path = repo_path.resolve()
    start = time.monotonic()
    if config is None:
        config = DriftConfig.load(repo_path)

    changed_files: list[str] = []
    try:
        if diff_mode == "staged":
            git_args = ["git", "diff", "--cached", "--name-only"]
        elif diff_mode == "uncommitted":
            git_args = ["git", "diff", "--name-only", "HEAD"]
        else:
            git_args = ["git", "diff", "--name-only", diff_ref]

        result = subprocess.run(
            git_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        changed_files = [line for line in result.stdout.strip().splitlines() if line]
    except Exception as exc:
        logger.warning(
            "Could not resolve diff mode '%s' (ref='%s'): %s. Falling back to full analysis.",
            diff_mode,
            diff_ref,
            exc,
        )
        analysis = analyze_repo(
            repo_path,
            config,
            since_days=since_days,
            target_path=target_path,
            workers=workers,
        )
        degradation_cause = "diff_ref_invalid" if diff_mode == "ref" else "git_diff_query_failed"
        _mark_analysis_degraded(
            analysis,
            cause=degradation_cause,
            component="git_diff",
            message="Diff reference could not be resolved; executed full-repository fallback.",
            details={"diff_ref": diff_ref, "diff_mode": diff_mode, "error": str(exc)},
        )
        return analysis

    # Map git-root-relative paths to repo-relative paths when repo_path is
    # a subdirectory of the git root (#117).
    from drift.ingestion.git_history import _git_repo_prefix

    prefix = _git_repo_prefix(repo_path)
    if prefix:
        mapped: list[str] = []
        for fp in changed_files:
            if fp.startswith(prefix):
                mapped.append(fp[len(prefix):])
        changed_files = mapped

    if not changed_files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )

    discover_started_at = time.monotonic()
    all_files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
        max_files=config.thresholds.max_discovery_files,
        ts_enabled=config.languages.typescript,
    )
    changed_set = set(changed_files)
    files = [f for f in all_files if f.path.as_posix() in changed_set]

    if target_path:
        target = Path(target_path).as_posix().strip("/")
        if target:
            files = [
                f
                for f in files
                if (
                    f.path.as_posix().strip("/") == target
                    or f.path.as_posix().strip("/").startswith(target + "/")
                )
            ]
    discover_duration_seconds = round(
        max(0.0, time.monotonic() - discover_started_at),
        3,
    )

    if not files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )

    effective_workers = resolve_worker_count(
        config=config,
        files=files,
        requested_workers=workers,
    )

    analysis = _run_pipeline(
        repo_path,
        files,
        config,
        since_days=since_days,
        on_progress=on_progress,
        workers=effective_workers,
        discover_duration_seconds=discover_duration_seconds,
    )
    analysis.analysis_duration_seconds = round(time.monotonic() - start, 2)
    analysis.phase_timings["discover_seconds"] = discover_duration_seconds
    analysis.phase_timings["total_seconds"] = analysis.analysis_duration_seconds

    _apply_trend_and_persist_snapshot(
        repo_path,
        config,
        analysis,
        scope="diff",
    )

    return analysis
