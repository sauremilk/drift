"""Main analysis orchestrator — coordinates ingestion, signals, and scoring."""

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.ingestion.git_history import build_file_histories, parse_git_history
from drift.models import (
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    RepoAnalysis,
)
from drift.scoring.engine import (
    composite_score,
    compute_module_scores,
    compute_signal_scores,
)
from drift.signals.architecture_violation import ArchitectureViolationSignal
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal
from drift.signals.mutant_duplicates import MutantDuplicateSignal
from drift.signals.pattern_fragmentation import PatternFragmentationSignal
from drift.signals.system_misalignment import SystemMisalignmentSignal
from drift.signals.temporal_volatility import TemporalVolatilitySignal

# Progress callback: (phase_name, current, total)
ProgressCallback = Callable[[str, int, int], None]

# Default parallelism for file parsing — threads work well here because
# the bottleneck is disk I/O rather than pure CPU.
_DEFAULT_WORKERS = 8


def _fetch_git_history(
    repo_path: Path, since_days: int, known_files: set[str]
) -> tuple[list, dict]:
    """Run git history parsing (designed to run in a background thread)."""
    commits = parse_git_history(
        repo_path, since_days=since_days, file_filter=known_files
    )
    file_histories = build_file_histories(commits, known_files=known_files)
    return commits, file_histories


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

    Returns:
        Complete RepoAnalysis with scores, findings, and module breakdowns.
    """
    start = time.monotonic()
    repo_path = repo_path.resolve()

    if config is None:
        config = DriftConfig.load(repo_path)

    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    # --- 1. File discovery ---
    _progress("Discovering files", 0, 0)
    files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
    )

    if target_path:
        target = Path(target_path)
        files = [f for f in files if str(f.path).startswith(str(target))]

    # --- 2. AST parsing (parallelized) + 3. Git history (concurrent) ---
    known_files = {f.path.as_posix() for f in files}

    # Initialise cache (also creates the .drift-cache/parse directory).
    cache = ParseCache(repo_path / config.cache_dir)

    # Pre-classify files into cache hits and files that need parsing.
    cached_results: dict[int, ParseResult] = {}
    to_parse: list[tuple[int, object]] = []  # (index, finfo)
    for idx, finfo in enumerate(files):
        full_path = repo_path / finfo.path
        try:
            content_hash = ParseCache.file_hash(full_path)
            hit = cache.get(content_hash)
            if hit is not None:
                cached_results[idx] = hit
                continue
        except OSError:
            pass
        to_parse.append((idx, finfo))

    _progress("Parsing files", len(cached_results), len(files))

    # Launch git history in a background thread while we parse AST files.
    executor = ThreadPoolExecutor(max_workers=workers)
    git_future = executor.submit(_fetch_git_history, repo_path, since_days, known_files)

    # Parse uncached files in parallel.
    parse_results: list[ParseResult] = [None] * len(files)  # type: ignore[list-item]
    for idx, cached in cached_results.items():
        parse_results[idx] = cached

    if to_parse:
        new_results: list[tuple[int, str, ParseResult]] = [None] * len(to_parse)  # type: ignore[list-item]
        futures = {
            executor.submit(parse_file, finfo.path, repo_path, finfo.language): (i, idx, finfo)
            for i, (idx, finfo) in enumerate(to_parse)
        }
        for future in as_completed(futures):
            i, idx, finfo = futures[future]
            result = future.result()
            parse_results[idx] = result
            try:
                full_path = repo_path / finfo.path
                content_hash = ParseCache.file_hash(full_path)
                new_results[i] = (idx, content_hash, result)
            except OSError:
                pass

        # Populate cache (main thread, no races).
        for entry in new_results:
            if entry is not None:
                _idx, h, r = entry
                cache.put(h, r)

    _progress("Parsing files", len(files), len(files))

    # Collect git results.
    commits, file_histories = git_future.result()
    executor.shutdown(wait=False)

    _progress("Analyzing git history", 0, 0)
    signals = [
        PatternFragmentationSignal(),
        ArchitectureViolationSignal(),
        MutantDuplicateSignal(repo_path),
        ExplainabilityDeficitSignal(),
        TemporalVolatilitySignal(),
        SystemMisalignmentSignal(),
        # DocImplDriftSignal excluded — Phase 2 stub (weight 0.0)
    ]

    all_findings: list[Finding] = []
    total_signals = len(signals)
    for i, signal in enumerate(signals):
        _progress(f"Signal: {signal.name}", i + 1, total_signals)
        findings = signal.analyze(parse_results, file_histories, config)
        all_findings.extend(findings)

    # --- 5. Scoring ---
    signal_scores = compute_signal_scores(all_findings)
    repo_score = composite_score(signal_scores, config.weights)
    module_scores = compute_module_scores(all_findings, config.weights)

    # --- 6. Pattern catalog ---
    pattern_catalog: dict[PatternCategory, list[PatternInstance]] = {}
    for pr in parse_results:
        for pattern in pr.patterns:
            pattern_catalog.setdefault(pattern.category, []).append(pattern)

    # --- 7. AI attribution ratio ---
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
    )


def analyze_diff(
    repo_path: Path,
    config: DriftConfig | None = None,
    diff_ref: str = "HEAD~1",
    workers: int = _DEFAULT_WORKERS,
) -> RepoAnalysis:
    """Analyze only files changed since a given git ref.

    Useful for CI — only checks files in the current diff.
    Runs signals only on changed files rather than the entire repo.
    """

    logger = logging.getLogger("drift")
    repo_path = repo_path.resolve()

    if config is None:
        config = DriftConfig.load(repo_path)

    # Get changed files from git
    changed_files: list[str] = []
    try:
        import git

        repo = git.Repo(repo_path, search_parent_directories=True)
        diff_index = repo.head.commit.diff(diff_ref)
        for diff_item in diff_index:
            if diff_item.a_path:
                changed_files.append(diff_item.a_path)
            if diff_item.b_path and diff_item.b_path != diff_item.a_path:
                changed_files.append(diff_item.b_path)
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

    # Run targeted analysis on changed files only
    start = time.monotonic()

    # --- 1. File discovery (only changed files) ---
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

    # --- 2. AST parsing (parallelized) + 3. Git history (concurrent) ---
    known_files = {f.path.as_posix() for f in files}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        git_future = executor.submit(_fetch_git_history, repo_path, 90, known_files)
        parse_results: list[ParseResult] = [None] * len(files)  # type: ignore[list-item]
        futures = {
            executor.submit(parse_file, finfo.path, repo_path, finfo.language): idx
            for idx, finfo in enumerate(files)
        }
        for future in as_completed(futures):
            parse_results[futures[future]] = future.result()
        commits, file_histories = git_future.result()

    # --- 4. Run signals ---
    signals = [
        PatternFragmentationSignal(),
        ArchitectureViolationSignal(),
        MutantDuplicateSignal(repo_path),
        ExplainabilityDeficitSignal(),
        TemporalVolatilitySignal(),
        SystemMisalignmentSignal(),
        # DocImplDriftSignal excluded — Phase 2 stub (weight 0.0)
    ]

    all_findings: list[Finding] = []
    for signal in signals:
        findings = signal.analyze(parse_results, file_histories, config)
        all_findings.extend(findings)

    # --- 5. Scoring ---
    signal_scores = compute_signal_scores(all_findings)
    score = composite_score(signal_scores, config.weights)
    module_scores = compute_module_scores(all_findings, config.weights)

    duration = time.monotonic() - start

    return RepoAnalysis(
        repo_path=repo_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=score,
        module_scores=module_scores,
        findings=all_findings,
        total_files=len(files),
        total_functions=sum(len(pr.functions) for pr in parse_results),
        ai_attributed_ratio=round(
            sum(1 for c in commits if c.is_ai_attributed) / max(1, len(commits)), 3
        ),
        analysis_duration_seconds=round(duration, 2),
    )
