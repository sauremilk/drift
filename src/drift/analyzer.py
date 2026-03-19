"""Main analysis orchestrator — coordinates ingestion, signals, and scoring."""

from __future__ import annotations

import datetime
import logging
import time
from pathlib import Path
from typing import Callable

from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.ingestion.git_history import build_file_histories, parse_git_history
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    RepoAnalysis,
    SignalType,
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


def analyze_repo(
    repo_path: Path,
    config: DriftConfig | None = None,
    since_days: int = 90,
    target_path: str | None = None,
    on_progress: ProgressCallback | None = None,
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

    # --- 2. AST parsing (with cache) ---
    cache_dir = repo_path / config.cache_dir
    cache = ParseCache(cache_dir)
    logger = logging.getLogger("drift")

    parse_results: list[ParseResult] = []
    total_files = len(files)
    for i, finfo in enumerate(files):
        _progress("Parsing files", i + 1, total_files)
        full_path = repo_path / finfo.path
        try:
            content_hash = ParseCache.file_hash(full_path)
        except OSError:
            result = parse_file(finfo.path, repo_path, finfo.language)
            parse_results.append(result)
            continue

        cached = cache.get(content_hash)
        if cached is not None:
            parse_results.append(cached)
        else:
            result = parse_file(finfo.path, repo_path, finfo.language)
            cache.put(content_hash, result)
            parse_results.append(result)

    # --- 3. Git history ---
    _progress("Analyzing git history", 0, 0)
    known_files = {f.path.as_posix() for f in files}
    commits = parse_git_history(
        repo_path, since_days=since_days, file_filter=known_files
    )
    file_histories = build_file_histories(commits, known_files=known_files)

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
        analyzed_at=datetime.datetime.now(tz=datetime.timezone.utc),
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
) -> RepoAnalysis:
    """Analyze only files changed since a given git ref.

    Useful for CI — only checks files in the current diff.
    Runs signals only on changed files rather than the entire repo.
    """
    import logging

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
        return analyze_repo(repo_path, config)

    if not changed_files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.timezone.utc),
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
            analyzed_at=datetime.datetime.now(tz=datetime.timezone.utc),
            drift_score=0.0,
        )

    # --- 2. AST parsing ---
    parse_results: list[ParseResult] = []
    for finfo in files:
        result = parse_file(finfo.path, repo_path, finfo.language)
        parse_results.append(result)

    # --- 3. Git history ---
    known_files = {f.path.as_posix() for f in files}
    commits = parse_git_history(repo_path, since_days=90, file_filter=known_files)
    file_histories = build_file_histories(commits, known_files=known_files)

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
        analyzed_at=datetime.datetime.now(tz=datetime.timezone.utc),
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
