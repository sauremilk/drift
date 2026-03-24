"""Main analysis orchestrator — coordinates ingestion, signals, and scoring."""

from __future__ import annotations

import datetime
import importlib
import logging
import pkgutil
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import drift.signals
from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.embeddings import get_embedding_service
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.ingestion.git_history import build_file_histories, parse_git_history
from drift.models import (
    FileInfo,
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    RepoAnalysis,
)
from drift.scoring.engine import (
    assign_impact_scores,
    composite_score,
    compute_module_scores,
    compute_signal_scores,
)
from drift.signals.base import AnalysisContext, create_signals

# Auto-discover all signal modules so @register_signal decorators execute.
for _finder, _mod_name, _ispkg in pkgutil.iter_modules(drift.signals.__path__):
    importlib.import_module(f"drift.signals.{_mod_name}")

# Progress callback: (phase_name, current, total)
ProgressCallback = Callable[[str, int, int], None]

# Default parallelism for file parsing — threads work well here because
# the bottleneck is disk I/O rather than pure CPU.
_DEFAULT_WORKERS = 8


def _is_git_repo(path: Path) -> bool:
    """Check whether *path* is inside a git working tree."""
    try:
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _fetch_git_history(
    repo_path: Path, since_days: int, known_files: set[str]
) -> tuple[list, dict]:
    """Run git history parsing (designed to run in a background thread)."""
    commits = parse_git_history(repo_path, since_days=since_days, file_filter=known_files)
    file_histories = build_file_histories(commits, known_files=known_files)
    return commits, file_histories


def _run_pipeline(
    repo_path: Path,
    files: list[FileInfo],
    config: DriftConfig,
    since_days: int = 90,
    on_progress: ProgressCallback | None = None,
    workers: int = _DEFAULT_WORKERS,
    _start: float | None = None,
) -> RepoAnalysis:
    """Shared analysis pipeline: parse → git history → signals → score.

    Both ``analyze_repo`` and ``analyze_diff`` delegate here after resolving
    which files to analyse.  Keeping the pipeline in one place eliminates
    duplication and ensures every code-path benefits from caching, progress
    reporting, and resilient signal execution.
    """
    start = _start if _start is not None else time.monotonic()

    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    known_files = {f.path.as_posix() for f in files}

    # --- 1. AST parsing (parallelized, cache-aware) ---
    cache = ParseCache(repo_path / config.cache_dir)

    cached_results: dict[int, ParseResult] = {}
    # Keep the content hash for cache misses so we don't re-read each file
    # after parsing just to compute the key again.
    to_parse: list[tuple[int, FileInfo, str | None]] = []
    for idx, finfo in enumerate(files):
        full_path = repo_path / finfo.path
        content_hash: str | None = None
        try:
            content_hash = ParseCache.file_hash(full_path)
            hit = cache.get(content_hash)
            if hit is not None:
                cached_results[idx] = hit
                continue
        except OSError:
            pass
        to_parse.append((idx, finfo, content_hash))

    _progress("Parsing files", len(cached_results), len(files))

    has_git = _is_git_repo(repo_path)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # --- 2. Git history (concurrent with parsing) ---
        git_future = (
            executor.submit(_fetch_git_history, repo_path, since_days, known_files)
            if has_git
            else None
        )

        parse_results: list[ParseResult] = [None] * len(files)  # type: ignore[list-item]
        for idx, cached in cached_results.items():
            parse_results[idx] = cached

        if to_parse:
            new_results: list[tuple[int, str, ParseResult]] = [None] * len(to_parse)  # type: ignore[list-item]
            futures = {
                executor.submit(parse_file, finfo.path, repo_path, finfo.language): (
                    i,
                    idx,
                    content_hash,
                )
                for i, (idx, finfo, content_hash) in enumerate(to_parse)
            }
            for future in as_completed(futures):
                i, idx, content_hash = futures[future]
                result = future.result()
                parse_results[idx] = result
                if content_hash is not None:
                    new_results[i] = (idx, content_hash, result)

            for entry in new_results:
                if entry is not None:
                    _idx, h, r = entry
                    cache.put(h, r)

        _progress("Parsing files", len(files), len(files))

        if git_future is not None:
            commits, file_histories = git_future.result()
        else:
            logging.getLogger("drift").info("Not a git repository — skipping git history analysis.")
            commits, file_histories = [], {}

    _progress("Analyzing git history", 0, 0)

    # --- 3. Embedding service ---
    emb_svc = None
    if config.embeddings_enabled:
        emb_svc = get_embedding_service(
            cache_dir=repo_path / config.cache_dir,
            model_name=config.embedding_model,
            batch_size=config.embedding_batch_size,
        )

    # --- 4. Signals ---
    ctx = AnalysisContext(
        repo_path=repo_path,
        config=config,
        parse_results=parse_results,
        file_histories=file_histories,
        embedding_service=emb_svc,
    )
    signals = create_signals(ctx)

    all_findings: list[Finding] = []
    total_signals = len(signals)
    for i, signal in enumerate(signals):
        _progress(f"Signal: {signal.name}", i + 1, total_signals)
        try:
            findings = signal.analyze(parse_results, file_histories, config)
            all_findings.extend(findings)
        except Exception:
            logging.getLogger("drift").warning(
                "Signal '%s' failed; skipping.",
                signal.name,
                exc_info=True,
            )

    # --- 5. Scoring ---
    assign_impact_scores(all_findings, config.weights)
    signal_scores = compute_signal_scores(all_findings)
    repo_score = composite_score(signal_scores, config.weights)
    module_scores = compute_module_scores(all_findings, config.weights)

    # --- 6. Pattern catalog ---
    pattern_catalog: dict[PatternCategory, list[PatternInstance]] = {}
    for pr in parse_results:
        for pattern in pr.patterns:
            pattern_catalog.setdefault(pattern.category, []).append(pattern)

    # --- 7. Assemble result ---
    total_funcs = sum(len(pr.functions) for pr in parse_results)
    ai_commits = sum(1 for c in commits if c.is_ai_attributed)
    ai_ratio = ai_commits / max(1, len(commits))

    duration = time.monotonic() - start

    return RepoAnalysis(
        repo_path=repo_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=repo_score,
        module_scores=module_scores,
        findings=all_findings,
        pattern_catalog=pattern_catalog,
        total_files=len(files),
        total_functions=total_funcs,
        ai_attributed_ratio=round(ai_ratio, 3),
        analysis_duration_seconds=round(duration, 2),
        commits=commits,
        file_histories=file_histories,
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
    workers: int = _DEFAULT_WORKERS,
) -> RepoAnalysis:
    """Run full drift analysis on a repository.

    Args:
        repo_path: Absolute path to the repository root.
        config: Drift configuration. Loaded from drift.yaml if None.
        since_days: How many days of git history to analyze.
        target_path: Optional subdirectory to restrict analysis to.
        on_progress: Optional callback (phase, current, total) for progress display.
        workers: Number of parallel parsing threads.

    Returns:
        Complete RepoAnalysis with scores, findings, and module breakdowns.
    """
    repo_path = repo_path.resolve()
    start = time.monotonic()

    if config is None:
        config = DriftConfig.load(repo_path)

    if on_progress:
        on_progress("Discovering files", 0, 0)

    files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
    )

    if target_path:
        target = Path(target_path)
        files = [f for f in files if str(f.path).startswith(str(target))]

    return _run_pipeline(
        repo_path, files, config,
        since_days=since_days,
        on_progress=on_progress,
        workers=workers,
        _start=start,
    )


def analyze_diff(
    repo_path: Path,
    config: DriftConfig | None = None,
    diff_ref: str = "HEAD~1",
    workers: int = _DEFAULT_WORKERS,
    on_progress: ProgressCallback | None = None,
) -> RepoAnalysis:
    """Analyze only files changed since a given git ref.

    Useful for CI — only checks files in the current diff.
    Runs signals only on changed files rather than the entire repo.
    """
    logger = logging.getLogger("drift")
    repo_path = repo_path.resolve()
    start = time.monotonic()

    if config is None:
        config = DriftConfig.load(repo_path)

    # Get changed files from git (subprocess per ADR-004)
    changed_files: list[str] = []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_ref],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
        )
        changed_files = [line for line in result.stdout.strip().splitlines() if line]
    except Exception as exc:
        logger.warning(
            "Could not resolve diff ref '%s': %s. Falling back to full analysis.",
            diff_ref,
            exc,
        )
        return analyze_repo(repo_path, config, workers=workers)

    if not changed_files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )

    all_files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
    )
    changed_set = set(changed_files)
    files = [f for f in all_files if f.path.as_posix() in changed_set]

    if not files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )

    return _run_pipeline(
        repo_path, files, config,
        since_days=90,
        on_progress=on_progress,
        workers=workers,
        _start=start,
    )
