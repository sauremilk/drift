"""Composable analysis pipeline phases for repository and diff analysis.

This module is **stateless**: every function receives its inputs explicitly
and returns results without mutating shared state.  It does not import or
manage session state — that responsibility belongs to ``drift.session``.

Architectural invariant (Phase-5 boundary contract):
    pipeline.py  → stateless, single-run transformation graph
    session.py   → stateful, multi-call orchestration context
"""

from __future__ import annotations

import datetime
import logging
import os
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from drift.cache import ParseCache, SignalCache
from drift.context_tags import apply_context_tags, scan_context_tags
from drift.embeddings import get_embedding_service
from drift.finding_context import annotate_finding_contexts
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.git_history import (
    build_file_histories,
    detect_ai_tool_indicators,
    indicator_boost_for_tools,
    parse_git_history,
)
from drift.models import (
    CommitInfo,
    FileHistory,
    FileInfo,
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    RepoAnalysis,
)
from drift.scoring.engine import (
    apply_path_overrides,
    assign_impact_scores,
    auto_calibrate_weights,
    composite_score,
    compute_module_scores,
    compute_signal_scores,
)
from drift.signals.base import (
    AnalysisContext,
    BaseSignal,
    SignalCapabilities,
    create_signals,
)
from drift.suppression import filter_findings, scan_suppressions

if TYPE_CHECKING:
    from pathlib import Path

    from drift.config import DriftConfig

ProgressCallback = Callable[[str, int, int], None]

_GIT_HISTORY_CACHE_TTL_SECONDS = 600.0
_GIT_HISTORY_CACHE_MAX_ENTRIES = 16
_GIT_HISTORY_CACHE_LOCK = threading.RLock()
_GIT_HISTORY_CACHE: dict[
    tuple[str, str, int, float, float, frozenset[str]],
    tuple[float, list[CommitInfo], dict[str, FileHistory]],
] = {}


def _determine_default_workers() -> int:
    """Return a conservative machine-adaptive worker default.

    Priority:
    1) ``DRIFT_WORKERS`` environment override (integer >= 1)
    2) CPU-based fallback in [2, 16]
    """

    env_override = os.getenv("DRIFT_WORKERS")
    if env_override:
        try:
            value = int(env_override)
            if value >= 1:
                return value
        except ValueError:
            pass
        logging.getLogger("drift").warning(
            "Ignoring invalid DRIFT_WORKERS=%r; using auto worker count.",
            env_override,
        )

    cpu = os.cpu_count() or 8
    return max(2, min(16, cpu))


DEFAULT_WORKERS = _determine_default_workers()


@dataclass(slots=True)
class DegradationInfo:
    """Machine-readable degradation metadata attached to an analysis run."""

    causes: set[str]
    components: set[str]
    events: list[dict[str, object]]


@dataclass(slots=True)
class ParsedInputs:
    """Output of the ingestion phase."""

    parse_results: list[ParseResult]
    commits: list[CommitInfo]
    file_histories: dict[str, FileHistory]
    ai_tools_detected: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SignalOutput:
    """Output of the signal execution phase."""

    findings: list[Finding]


@dataclass(slots=True)
class ScoredFindings:
    """Output of scoring and post-processing."""

    findings: list[Finding]
    repo_score: float
    module_scores: list
    suppressed_count: int
    context_tagged_count: int
    suppressed_findings: list[Finding] = field(default_factory=list)


@dataclass(slots=True)
class PipelineArtifacts:
    """Complete intermediate artifacts required for final assembly."""

    parsed: ParsedInputs
    signaled: SignalOutput
    scored: ScoredFindings
    degradation: DegradationInfo


def make_degradation_event(
    *,
    cause: str,
    component: str,
    message: str,
    details: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a machine-readable degradation event payload."""
    event: dict[str, object] = {
        "cause": cause,
        "component": component,
        "message": message,
    }
    if details:
        event["details"] = details
    return event


def is_git_repo(path: Path) -> bool:
    """Check whether *path* is inside a git working tree.

    Result is cached per resolved path with a short TTL to avoid
    repeated subprocess spawns on consecutive pipeline runs.
    """
    return _is_git_repo_cached(path.resolve().as_posix())


# Short-lived cache for is_git_repo to eliminate redundant subprocess calls.
_IS_GIT_REPO_CACHE_LOCK = threading.Lock()
_IS_GIT_REPO_CACHE: dict[str, tuple[float, bool]] = {}
_IS_GIT_REPO_CACHE_TTL = 60.0


def _is_git_repo_cached(posix_key: str) -> bool:
    """Cached check — avoids spawning git rev-parse on every call."""
    now = time.monotonic()
    with _IS_GIT_REPO_CACHE_LOCK:
        cached = _IS_GIT_REPO_CACHE.get(posix_key)
        if cached is not None and (now - cached[0]) < _IS_GIT_REPO_CACHE_TTL:
            return cached[1]

    try:
        subprocess.run(
            ["git", "-C", posix_key, "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        result = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        result = False

    with _IS_GIT_REPO_CACHE_LOCK:
        _IS_GIT_REPO_CACHE[posix_key] = (now, result)
    return result


def _current_git_head(path: Path) -> str | None:
    """Return current HEAD SHA for cache invalidation, or None on failure.

    Uses a short-lived per-path cache (5 s) so that consecutive calls
    within the same pipeline run (ingestion check + fetch_git_history)
    do not spawn redundant subprocesses.
    """
    posix_key = path.resolve().as_posix()
    now = time.monotonic()
    with _GIT_HEAD_CACHE_LOCK:
        cached = _GIT_HEAD_CACHE.get(posix_key)
        if cached is not None and (now - cached[0]) < _GIT_HEAD_CACHE_TTL:
            return cached[1]

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=5,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        with _GIT_HEAD_CACHE_LOCK:
            _GIT_HEAD_CACHE[posix_key] = (now, None)
        return None

    head = result.stdout.strip() or None
    with _GIT_HEAD_CACHE_LOCK:
        _GIT_HEAD_CACHE[posix_key] = (now, head)
    return head


# Short-lived HEAD SHA cache to deduplicate subprocess calls within a run.
_GIT_HEAD_CACHE_LOCK = threading.Lock()
_GIT_HEAD_CACHE: dict[str, tuple[float, str | None]] = {}
_GIT_HEAD_CACHE_TTL = 5.0


def _prune_git_history_cache(now: float) -> None:
    """Drop stale entries and enforce bounded cache size."""
    stale = [
        key for key, (cached_at, _commits, _histories) in _GIT_HISTORY_CACHE.items()
        if now - cached_at > _GIT_HISTORY_CACHE_TTL_SECONDS
    ]
    for key in stale:
        _GIT_HISTORY_CACHE.pop(key, None)

    while len(_GIT_HISTORY_CACHE) > _GIT_HISTORY_CACHE_MAX_ENTRIES:
        oldest_key = min(
            _GIT_HISTORY_CACHE,
            key=lambda item: _GIT_HISTORY_CACHE[item][0],
        )
        _GIT_HISTORY_CACHE.pop(oldest_key, None)


def fetch_git_history(
    repo_path: Path,
    since_days: int,
    known_files: set[str],
    ai_confidence_threshold: float = 0.50,
    indicator_boost: float = 0.0,
) -> tuple[list[CommitInfo], dict[str, FileHistory]]:
    """Run git history parsing (designed to run in a background thread).

    Uses a short-lived in-process cache keyed by repo head and analysis
    parameters to avoid repeated expensive git-log parsing across consecutive
    scans with unchanged commit history.
    """
    cache_key: tuple[str, str, int, float, float, frozenset[str]] | None = None
    head_sha = _current_git_head(repo_path)
    if head_sha is not None:
        cache_key = (
            repo_path.resolve().as_posix(),
            head_sha,
            since_days,
            round(ai_confidence_threshold, 6),
            round(indicator_boost, 6),
            frozenset(known_files),
        )
        now = time.monotonic()
        with _GIT_HISTORY_CACHE_LOCK:
            cached = _GIT_HISTORY_CACHE.get(cache_key)
            if cached is not None:
                cached_at, cached_commits, cached_histories = cached
                if now - cached_at <= _GIT_HISTORY_CACHE_TTL_SECONDS:
                    return list(cached_commits), dict(cached_histories)

    commits = parse_git_history(
        repo_path,
        since_days=since_days,
        file_filter=known_files,
        ai_confidence_threshold=ai_confidence_threshold,
        indicator_boost=indicator_boost,
    )
    file_histories = build_file_histories(commits, known_files=known_files)

    if cache_key is not None:
        now = time.monotonic()
        with _GIT_HISTORY_CACHE_LOCK:
            _GIT_HISTORY_CACHE[cache_key] = (now, list(commits), dict(file_histories))
            _prune_git_history_cache(now)

    return commits, file_histories


class IngestionPhase:
    """File parsing and git-history retrieval."""

    def __init__(
        self,
        *,
        cache_factory: Callable[[Path], ParseCache] = ParseCache,
        parse_file_fn: Callable[[Path, Path, str], ParseResult] = parse_file,
        is_git_repo_fn: Callable[[Path], bool] = is_git_repo,
        fetch_git_history_fn: Callable[
            [Path, int, set[str], float, float],
            tuple[list[CommitInfo], dict[str, FileHistory]],
        ] = fetch_git_history,
    ) -> None:
        self._cache_factory = cache_factory
        self._parse_file = parse_file_fn
        self._is_git_repo = is_git_repo_fn
        self._fetch_git_history = fetch_git_history_fn

    def run(
        self,
        repo_path: Path,
        files: list[FileInfo],
        config: DriftConfig,
        *,
        since_days: int,
        workers: int,
        degradation: DegradationInfo,
        progress: ProgressCallback | None = None,
    ) -> ParsedInputs:
        """Parse source files and collect git context for downstream signal phases.

        The method first attempts content-hash cache hits, then parses only the
        remaining files in parallel while git history is fetched concurrently.
        On git failures, parsing results are preserved and degradation metadata is
        recorded so later stages can continue with reduced context.
        """
        known_files = {f.path.as_posix() for f in files}
        cache = self._cache_factory(repo_path / config.cache_dir)

        # Detect AI tool config files for indicator boost
        ai_tools = detect_ai_tool_indicators(repo_path)
        ai_boost = indicator_boost_for_tools(ai_tools)

        cached_results: dict[int, ParseResult] = {}
        to_parse: list[tuple[int, FileInfo, str | None]] = []
        file_hashes: dict[str, str] = {}
        for idx, finfo in enumerate(files):
            full_path = repo_path / finfo.path
            content_hash: str | None = None
            try:
                content_hash = ParseCache.file_hash(full_path)
                file_hashes[finfo.path.as_posix()] = content_hash
                hit = cache.get(content_hash)
                if hit is not None:
                    # Fix stale path: cache is keyed by content hash,
                    # so a hit may carry a file_path from a different
                    # file with identical content (#115).
                    if hit.file_path != finfo.path:
                        hit.file_path = finfo.path
                        for func in hit.functions:
                            func.file_path = finfo.path
                        for cls in hit.classes:
                            cls.file_path = finfo.path
                            for method in cls.methods:
                                method.file_path = finfo.path
                        for imp in hit.imports:
                            imp.source_file = finfo.path
                        for pattern in hit.patterns:
                            pattern.file_path = finfo.path
                    cached_results[idx] = hit
                    continue
            except OSError:
                pass
            to_parse.append((idx, finfo, content_hash))

        if progress:
            progress("Parsing files", len(cached_results), len(files))

        has_git = self._is_git_repo(repo_path)

        # Fast path for warm cache runs outside git repositories.
        if not to_parse and not has_git:
            parse_results = [cached_results[i] for i in range(len(files))]
            if progress:
                progress("Analyzing git history", 0, 0)
            return ParsedInputs(
                parse_results=parse_results,
                commits=[],
                file_histories={},
                ai_tools_detected=ai_tools,
                file_hashes=file_hashes,
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            git_future = (
                executor.submit(
                    self._fetch_git_history,
                    repo_path,
                    since_days,
                    known_files,
                    config.thresholds.ai_confidence_threshold,
                    ai_boost,
                )
                if has_git
                else None
            )

            parse_results_opt: list[ParseResult | None] = [None] * len(files)
            for idx, cached in cached_results.items():
                parse_results_opt[idx] = cached

            if to_parse:
                new_results: list[tuple[int, str, ParseResult]] = []
                futures = {
                    executor.submit(
                        self._parse_file,
                        finfo.path,
                        repo_path,
                        finfo.language,
                    ): (idx, content_hash)
                    for idx, finfo, content_hash in to_parse
                }
                for future in as_completed(futures):
                    idx, content_hash = futures[future]
                    result = future.result()
                    parse_results_opt[idx] = result
                    if content_hash is not None:
                        new_results.append((idx, content_hash, result))

                for _idx, h, r in new_results:
                    cache.put(h, r)

            missing = [i for i, pr in enumerate(parse_results_opt) if pr is None]
            if missing:
                msg = (
                    f"Parser pipeline produced incomplete results for {len(missing)} files. "
                    "This indicates a parsing failure before result materialization."
                )
                raise RuntimeError(
                    msg,
                )
            parse_results = [pr for pr in parse_results_opt if pr is not None]

            if progress:
                progress("Parsing files", len(files), len(files))

            if git_future is not None:
                try:
                    commits, file_histories = git_future.result()
                except Exception as exc:
                    logging.getLogger("drift").warning(
                        "Git history fetch failed; continuing without history.",
                        exc_info=True,
                    )
                    commits, file_histories = [], {}
                    degradation.causes.add("git_history_unavailable")
                    degradation.components.add("git_history")
                    degradation.events.append(
                        make_degradation_event(
                            cause="git_history_unavailable",
                            component="git_history",
                            message=(
                                "Git history parsing failed; temporal/git-based "
                                "context omitted."
                            ),
                            details={"error": str(exc)},
                        ),
                    )
            else:
                logging.getLogger("drift").info(
                    "Not a git repository - skipping git history analysis.",
                )
                commits, file_histories = [], {}

        if progress:
            progress("Analyzing git history", 0, 0)

        return ParsedInputs(
            parse_results=parse_results,
            commits=commits,
            file_histories=file_histories,
            ai_tools_detected=ai_tools,
            file_hashes=file_hashes,
        )


class SignalPhase:
    """Signal execution with resilient failure handling.

    Signals run in parallel via ThreadPoolExecutor because they operate
    on shared *immutable* state (parse_results, file_histories, commits).
    No signal writes to shared data, so concurrent reads are safe.
    """

    def __init__(
        self,
        *,
        embedding_factory: Callable[..., Any] = get_embedding_service,
        signal_factory: Callable[..., list[BaseSignal]] = create_signals,
    ) -> None:
        self._embedding_factory = embedding_factory
        self._signal_factory = signal_factory

    def run(
        self,
        repo_path: Path,
        config: DriftConfig,
        parsed: ParsedInputs,
        *,
        degradation: DegradationInfo,
        progress: ProgressCallback | None = None,
        workers: int = DEFAULT_WORKERS,
        active_signals: set[str] | None = None,
    ) -> SignalOutput:
        """Execute enabled signals with optional embedding support and result caching.

        Signals are filtered by ``active_signals`` when provided, then executed
        through a cache-aware wrapper that reuses stable results based on config
        and parsed-content fingerprints. Failures are captured in degradation
        metadata instead of aborting the whole analysis pipeline.
        """
        ctx = AnalysisContext(
            repo_path=repo_path,
            config=config,
            parse_results=parsed.parse_results,
            file_histories=parsed.file_histories,
            embedding_service=None,
            commits=parsed.commits,
        )
        try:
            signals = self._signal_factory(ctx, active_signals=active_signals)
        except TypeError:
            # Backward-compatible fallback for custom factories that only accept ctx.
            signals = self._signal_factory(ctx)
            if active_signals is not None:
                filtered_signals: list[BaseSignal] = []
                for signal in signals:
                    sig_type = getattr(signal, "signal_type", None)
                    if sig_type is not None and sig_type.value in active_signals:
                        filtered_signals.append(signal)
                signals = filtered_signals
        total_signals = len(signals)

        if total_signals == 0:
            return SignalOutput(findings=[])

        emb_svc = None
        if config.embeddings_enabled:
            needs_embeddings = any(
                getattr(signal, "uses_embeddings", False)
                for signal in signals
            )
            if needs_embeddings:
                emb_svc = self._embedding_factory(
                    cache_dir=repo_path / config.cache_dir,
                    model_name=config.embedding_model,
                    batch_size=config.embedding_batch_size,
                )
                ctx.embedding_service = emb_svc
                capabilities = SignalCapabilities.from_analysis_context(ctx)
                for signal in signals:
                    signal.bind_context(capabilities)

        # --- signal-level result cache ---
        sig_cache = SignalCache(repo_path / config.cache_dir)
        config_fp = SignalCache.config_fingerprint(config)
        content_hash = SignalCache.content_hash_for_results(
            parsed.parse_results, parsed.file_hashes,
        )

        def _run_or_cache(signal: BaseSignal) -> list[Finding]:
            sig_type_enum = getattr(signal, "signal_type", None)
            sig_type = sig_type_enum.value if sig_type_enum is not None else None
            if sig_type is not None:
                cached = sig_cache.get(sig_type, config_fp, content_hash)
                if cached is not None:
                    return cached
            findings = signal.analyze(
                parsed.parse_results, parsed.file_histories, config,
            )
            if sig_type is not None:
                sig_cache.put(sig_type, config_fp, content_hash, findings)
            return findings

        # --- parallel signal execution ---
        completed_count = 0
        results: list[tuple[str, list[Finding]]] = []

        max_workers = min(total_signals, workers)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_or_cache, signal): signal
                for signal in signals
            }
            for future in as_completed(futures):
                signal = futures[future]
                completed_count += 1
                if progress:
                    progress(f"Signal: {signal.name}", completed_count, total_signals)
                try:
                    findings = future.result()
                    st_enum = getattr(signal, "signal_type", None)
                    sort_key = st_enum.value if st_enum is not None else signal.name
                    results.append((sort_key, findings))
                except Exception as exc:
                    logger = logging.getLogger("drift")
                    logger.warning(
                        "Signal '%s' failed; skipping. %s: %s",
                        signal.name,
                        type(exc).__name__,
                        exc,
                        exc_info=logger.isEnabledFor(logging.DEBUG),
                    )
                    degradation.causes.add("signal_failure")
                    degradation.components.add(f"signal:{signal.name}")
                    degradation.events.append(
                        make_degradation_event(
                            cause="signal_failure",
                            component=f"signal:{signal.name}",
                            message=f"Signal '{signal.name}' failed and was skipped.",
                            details={
                                "signal": signal.name,
                                "error_type": type(exc).__name__,
                                "error_message": str(exc),
                            },
                        ),
                    )

        # Sort by signal type to guarantee deterministic finding order
        # regardless of thread completion order.
        results.sort(key=lambda r: r[0])
        all_findings: list[Finding] = []
        for _sig_type, findings in results:
            all_findings.extend(findings)

        return SignalOutput(findings=all_findings)


class ScoringPhase:
    """Impact scoring, suppression, context tags, and final score aggregation."""

    def __init__(
        self,
        *,
        impact_assigner: Callable[..., None] = assign_impact_scores,
        suppression_scanner: Callable[..., dict] = scan_suppressions,
        suppression_filter: Callable[
            ...,
            tuple[list[Finding], list[Finding]],
        ] = filter_findings,
        context_scanner: Callable[..., dict] = scan_context_tags,
        context_applicator: Callable[
            ...,
            tuple[list[Finding], int],
        ] = apply_context_tags,
        calibrator: Callable[..., Any] = auto_calibrate_weights,
        signal_score_fn: Callable[..., dict] = compute_signal_scores,
        repo_score_fn: Callable[..., float] = composite_score,
        module_score_fn: Callable[..., list] = compute_module_scores,
    ) -> None:
        self._impact_assigner = impact_assigner
        self._suppression_scanner = suppression_scanner
        self._suppression_filter = suppression_filter
        self._context_scanner = context_scanner
        self._context_applicator = context_applicator
        self._calibrator = calibrator
        self._signal_score_fn = signal_score_fn
        self._repo_score_fn = repo_score_fn
        self._module_score_fn = module_score_fn

    def run(
        self,
        repo_path: Path,
        files: list[FileInfo],
        config: DriftConfig,
        findings: list[Finding],
        parse_results: list[ParseResult] | None = None,
    ) -> ScoredFindings:
        all_findings = findings
        self._impact_assigner(all_findings, config.weights)

        suppressions = self._suppression_scanner(files, repo_path)
        all_findings, suppressed_findings = self._suppression_filter(all_findings, suppressions)
        suppressed_count = len(suppressed_findings)

        ctx_tags = self._context_scanner(files, repo_path)
        all_findings, context_tagged_count = self._context_applicator(
            all_findings,
            ctx_tags,
            dampening=config.context_dampening,
        )
        self._impact_assigner(all_findings, config.weights)

        effective_weights = config.weights
        if config.auto_calibrate:
            effective_weights = self._calibrator(all_findings, config.weights)
            self._impact_assigner(all_findings, effective_weights)

        # Apply per-path overrides (filter + re-weight) before scoring
        if config.path_overrides:
            all_findings = apply_path_overrides(
                all_findings, config.path_overrides, effective_weights,
            )

        # Tag findings in deferred areas (still analysed, but flagged)
        if config.deferred:
            import fnmatch as _fnmatch

            for f in all_findings:
                if f.file_path is None:
                    continue
                posix = f.file_path.as_posix()
                for area in config.deferred:
                    if _fnmatch.fnmatch(posix, area.pattern):
                        f.deferred = True
                        if area.reason:
                            f.metadata.setdefault("deferred_reason", area.reason)
                        break

        # Classify every finding into an operational context for policy-aware triage.
        annotate_finding_contexts(all_findings, config)

        # Enrich findings with AST-based logical locations for agent navigation.
        from drift.logical_location import enrich_logical_locations

        if parse_results:
            enrich_logical_locations(all_findings, parse_results)

        n_modules = len({f.path.parent.as_posix() for f in files})
        is_small_repo = n_modules < config.thresholds.small_repo_module_threshold
        scoring_kwargs: dict[str, int] = {}
        if is_small_repo:
            scoring_kwargs["dampening_k"] = 20
            scoring_kwargs["min_findings"] = config.thresholds.small_repo_min_findings

        signal_scores = self._signal_score_fn(all_findings, **scoring_kwargs)
        repo_score = self._repo_score_fn(signal_scores, effective_weights)
        module_scores = self._module_score_fn(all_findings, effective_weights)

        return ScoredFindings(
            findings=all_findings,
            repo_score=repo_score,
            module_scores=module_scores,
            suppressed_count=suppressed_count,
            context_tagged_count=context_tagged_count,
            suppressed_findings=suppressed_findings,
        )


class ResultAssemblyPhase:
    """Final RepoAnalysis materialization from phase artifacts."""

    def run(
        self,
        repo_path: Path,
        files: list[FileInfo],
        artifacts: PipelineArtifacts,
        *,
        started_at: float,
        config: DriftConfig | None = None,
    ) -> RepoAnalysis:
        pattern_catalog: dict[PatternCategory, list[PatternInstance]] = {}
        for pr in artifacts.parsed.parse_results:
            for pattern in pr.patterns:
                pattern_catalog.setdefault(pattern.category, []).append(pattern)

        total_funcs = sum(len(pr.functions) for pr in artifacts.parsed.parse_results)
        ai_commits = sum(1 for c in artifacts.parsed.commits if c.is_ai_attributed)
        ai_ratio = ai_commits / max(1, len(artifacts.parsed.commits))

        # Manual override from drift.yaml policies.ai_attribution.manual_ratio
        manual_ratio = None
        if config is not None:
            manual_ratio = config.policies.ai_attribution.get("manual_ratio")
        if manual_ratio is not None:
            ai_ratio = float(manual_ratio)

        duration = time.monotonic() - started_at

        return RepoAnalysis(
            repo_path=repo_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=artifacts.scored.repo_score,
            module_scores=artifacts.scored.module_scores,
            findings=artifacts.scored.findings,
            suppressed_findings=artifacts.scored.suppressed_findings,
            pattern_catalog=pattern_catalog,
            total_files=len(files),
            total_functions=total_funcs,
            ai_attributed_ratio=round(ai_ratio, 3),
            analysis_duration_seconds=round(duration, 2),
            commits=artifacts.parsed.commits,
            file_histories=artifacts.parsed.file_histories,
            suppressed_count=artifacts.scored.suppressed_count,
            context_tagged_count=artifacts.scored.context_tagged_count,
            analysis_status=(
                "degraded" if artifacts.degradation.events else "complete"
            ),
            degradation_causes=sorted(artifacts.degradation.causes),
            degradation_components=sorted(artifacts.degradation.components),
            degradation_events=artifacts.degradation.events,
            ai_tools_detected=artifacts.parsed.ai_tools_detected,
        )


class AnalysisPipeline:
    """Composable analysis pipeline keeping each phase independently testable."""

    def __init__(
        self,
        *,
        ingestion_phase: IngestionPhase | None = None,
        signal_phase: SignalPhase | None = None,
        scoring_phase: ScoringPhase | None = None,
        result_assembly_phase: ResultAssemblyPhase | None = None,
    ) -> None:
        self._ingestion = ingestion_phase or IngestionPhase()
        self._signals = signal_phase or SignalPhase()
        self._scoring = scoring_phase or ScoringPhase()
        self._assembly = result_assembly_phase or ResultAssemblyPhase()

    def run(
        self,
        repo_path: Path,
        files: list[FileInfo],
        config: DriftConfig,
        *,
        since_days: int = 90,
        on_progress: ProgressCallback | None = None,
        workers: int = DEFAULT_WORKERS,
        active_signals: set[str] | None = None,
    ) -> RepoAnalysis:
        started_at = time.monotonic()
        degradation = DegradationInfo(causes=set(), components=set(), events=[])

        parsed = self._ingestion.run(
            repo_path,
            files,
            config,
            since_days=since_days,
            workers=workers,
            degradation=degradation,
            progress=on_progress,
        )
        signaled = self._signals.run(
            repo_path,
            config,
            parsed,
            degradation=degradation,
            progress=on_progress,
            workers=workers,
            active_signals=active_signals,
        )
        scored = self._scoring.run(
            repo_path, files, config, signaled.findings,
            parse_results=parsed.parse_results,
        )

        # Attribution enrichment (ADR-034): enrich findings with git-blame
        # provenance when enabled.  Runs after scoring, before assembly.
        if config.attribution.enabled:
            from drift.attribution import enrich_findings

            scored.findings = enrich_findings(
                scored.findings,
                repo_path,
                config.attribution,
                commits=parsed.commits,
            )

        return self._assembly.run(
            repo_path,
            files,
            PipelineArtifacts(
                parsed=parsed,
                signaled=signaled,
                scored=scored,
                degradation=degradation,
            ),
            started_at=started_at,
            config=config,
        )
