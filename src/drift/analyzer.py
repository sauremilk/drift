"""Main analysis orchestrator — coordinates ingestion, signals, and scoring."""

from __future__ import annotations

import datetime
import time
from pathlib import Path

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
from drift.signals.doc_impl_drift import DocImplDriftSignal
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal
from drift.signals.mutant_duplicates import MutantDuplicateSignal
from drift.signals.pattern_fragmentation import PatternFragmentationSignal
from drift.signals.system_misalignment import SystemMisalignmentSignal
from drift.signals.temporal_volatility import TemporalVolatilitySignal


def analyze_repo(
    repo_path: Path,
    config: DriftConfig | None = None,
    since_days: int = 90,
    target_path: str | None = None,
) -> RepoAnalysis:
    """Run full drift analysis on a repository.

    Args:
        repo_path: Absolute path to the repository root.
        config: Drift configuration. Loaded from drift.yaml if None.
        since_days: How many days of git history to analyze.
        target_path: Optional subdirectory to restrict analysis to.

    Returns:
        Complete RepoAnalysis with scores, findings, and module breakdowns.
    """
    start = time.monotonic()
    repo_path = repo_path.resolve()

    if config is None:
        config = DriftConfig.load(repo_path)

    # --- 1. File discovery ---
    files = discover_files(
        repo_path,
        include=config.include,
        exclude=config.exclude,
    )

    if target_path:
        target = Path(target_path)
        files = [f for f in files if str(f.path).startswith(str(target))]

    # --- 2. AST parsing ---
    parse_results: list[ParseResult] = []
    for finfo in files:
        result = parse_file(finfo.path, repo_path, finfo.language)
        parse_results.append(result)

    # --- 3. Git history ---
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
        DocImplDriftSignal(),
        SystemMisalignmentSignal(),
    ]

    all_findings: list[Finding] = []
    for signal in signals:
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
    """
    repo_path = repo_path.resolve()

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
    except Exception:
        # Fallback: analyze everything
        return analyze_repo(repo_path, config)

    if not changed_files:
        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.timezone.utc),
            drift_score=0.0,
        )

    # Run full analysis but filter to changed files
    analysis = analyze_repo(repo_path, config)

    changed_set = set(changed_files)
    filtered_findings = [
        f
        for f in analysis.findings
        if f.file_path and f.file_path.as_posix() in changed_set
    ]

    if config is None:
        config = DriftConfig.load(repo_path)

    signal_scores = compute_signal_scores(filtered_findings)
    score = composite_score(signal_scores, config.weights)

    analysis.findings = filtered_findings
    analysis.drift_score = score
    analysis.module_scores = compute_module_scores(filtered_findings, config.weights)

    return analysis
