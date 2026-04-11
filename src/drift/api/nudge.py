"""Nudge endpoint — incremental directional feedback after file changes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _log,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_DIFF_ACCEPT,
    DONE_SAFE_TO_COMMIT,
    _base_response,
    _error_response,
    _finding_concise,
    _next_step_contract,
    shape_for_profile,
    signal_abbrev,
)

if TYPE_CHECKING:
    from drift.incremental import BaselineSnapshot
    from drift.models import Finding, ParseResult

# Delta threshold above which safe_to_commit is False
_NUDGE_SIGNIFICANT_DELTA = 0.05

# Legacy module-level baseline store — kept for backward compatibility
# but nudge() now uses BaselineManager.instance() instead.
_baseline_store: dict[
    str,
    tuple[
        BaselineSnapshot,
        list[Finding],
        dict[str, ParseResult],
    ],
] = {}


def _is_derived_cache_artifact(path_str: str) -> bool:
    """Return True for derived drift cache artifacts (not source files)."""
    normalized = path_str.replace("\\", "/")
    top_level = normalized.split("/", 1)[0]
    return top_level.startswith(".drift-cache")


def _get_changed_files_from_git(
    repo_path: Path,
    *,
    uncommitted: bool = True,
) -> list[str] | None:
    """Return posix-relative paths of files changed in the working tree.

    Returns ``None`` when git is unavailable or fails, so callers can
    distinguish *no changes* (empty list) from *detection failed*.
    """
    import subprocess

    # ``--relative`` keeps the file list scoped to ``cwd`` (repo_path).
    # This avoids pulling unrelated dirty files from a parent git root when
    # nudge is executed on a sub-directory benchmark/project path.
    args = ["git", "diff", "--name-only", "--relative"]
    if uncommitted:
        args.append("HEAD")
    else:
        args.append("--cached")

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        return [line for line in proc.stdout.strip().splitlines() if line]
    except Exception:
        _log.warning(
            "Could not detect changed files via git in %s; "
            "nudge will analyse all discovered files.",
            repo_path,
        )
        return None


def _nudge_next_step_contract(*, safe_to_commit: bool) -> dict[str, Any]:
    """Build the next-step contract for nudge responses (ADR-024)."""
    if safe_to_commit:
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"staged_only": True},
            done_when=DONE_DIFF_ACCEPT,
        )
    return _next_step_contract(
        next_tool="drift_fix_plan",
        done_when=DONE_SAFE_TO_COMMIT,
        fallback_tool="drift_scan",
        fallback_params={"response_detail": "concise"},
    )


def nudge(
    path: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    uncommitted: bool = True,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Incremental directional feedback after file changes.

    Runs file-local signals on changed files with exact confidence and
    carries forward cross-file / git-dependent findings from the baseline
    with estimated confidence.

    If no baseline exists for the repository, a full scan is performed
    first to establish one.

    Parameters
    ----------
    path:
        Repository root directory.
    changed_files:
        Explicit list of changed file paths (posix, relative to repo root).
        Auto-detected via ``git diff`` when ``None``.
    uncommitted:
        When auto-detecting, use uncommitted working-tree changes (default)
        vs. staged-only.
    signals:
        Optional list of signal abbreviations to include in results.
        When set, only new/resolved findings matching these signals are returned.
    exclude_signals:
        Optional list of signal abbreviations to exclude from results.

    Returns
    -------
    dict
        Nudge response with direction, delta, safe_to_commit, confidence map,
        new/resolved findings, and agent instruction.
    """
    import time as _time

    from drift.incremental import BaselineSnapshot, IncrementalSignalRunner
    from drift.ingestion.ast_parser import parse_file
    from drift.ingestion.file_discovery import discover_files

    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()
    repo_key = repo_path.as_posix()

    params: dict[str, Any] = {
        "path": str(path),
        "changed_files": changed_files,
        "uncommitted": uncommitted,
    }
    parse_failed_files: list[dict[str, Any]] = []

    def record_parse_failure(
        *,
        file_path: str,
        stage: str,
        reason: str,
        errors: list[str] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "file": file_path,
            "stage": stage,
            "reason": reason,
        }
        if errors:
            entry["errors"] = list(errors)
        parse_failed_files.append(entry)

    def elapsed_ms() -> int:
        return int((_time.monotonic() - start_ms) * 1_000)

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        # -- Auto-detect changed files if not provided ----------------------
        git_detection_failed = False
        if changed_files is None:
            detected = _get_changed_files_from_git(
                repo_path, uncommitted=uncommitted
            )
            if detected is None:
                git_detection_failed = True
                changed_files = []
            else:
                changed_files = detected
        changed_set = set(changed_files)
        ignored_changed_files = sorted(
            fp for fp in changed_set if _is_derived_cache_artifact(fp)
        )
        if ignored_changed_files:
            changed_set.difference_update(ignored_changed_files)

        # -- Ensure baseline exists via BaselineManager (Phase 5) -----------
        from drift.incremental import BaselineManager

        mgr = BaselineManager.instance()
        stored = mgr.get(repo_path)
        baseline_refresh_reason: str | None = None

        if stored is None:
            baseline_refresh_reason = (
                mgr.consume_refresh_reason(repo_path) or "baseline_missing"
            )
            # Run full scan to create baseline
            from drift.analyzer import analyze_repo

            # Discover files once and reuse for both analysis and baseline.
            all_files = discover_files(
                repo_path,
                include=cfg.include,
                exclude=cfg.exclude,
                max_files=cfg.thresholds.max_discovery_files,
                cache_dir=cfg.cache_dir,
            )
            analysis = analyze_repo(repo_path, config=cfg)

            # Build file_hashes + parse_results map.
            # analyze_repo() already parsed all files via the pipeline,
            # so ParseCache will serve warm hits here — no re-parse cost
            # for unchanged files.
            from drift.cache import ParseCache

            pcache = ParseCache(repo_path / cfg.cache_dir)
            file_hashes: dict[str, str] = {}
            parse_map: dict[str, ParseResult] = {}
            for finfo in all_files:
                full_path = repo_path / finfo.path
                posix = finfo.path.as_posix()
                try:
                    h = ParseCache.file_hash(full_path)
                    file_hashes[posix] = h
                except OSError:
                    continue

                # Try cache first (warm from analyze_repo pipeline)
                cached_pr = pcache.get(h)
                if cached_pr is not None:
                    # Fix stale path from content-hash cache
                    if cached_pr.file_path != finfo.path:
                        cached_pr.file_path = finfo.path
                    parse_map[posix] = cached_pr
                    continue

                # Fallback: parse (should rarely happen after analyze_repo)
                try:
                    pr = parse_file(finfo.path, repo_path, finfo.language)
                    parse_map[posix] = pr
                    if pr.parse_errors:
                        record_parse_failure(
                            file_path=posix,
                            stage="baseline",
                            reason="parse_errors",
                            errors=pr.parse_errors,
                        )
                except Exception as exc:
                    record_parse_failure(
                        file_path=posix,
                        stage="baseline",
                        reason="parse_exception",
                        errors=[str(exc)],
                    )
                    continue

            baseline = BaselineSnapshot(
                file_hashes=file_hashes,
                score=analysis.drift_score,
            )
            mgr.store(repo_path, baseline, list(analysis.findings), parse_map)
            stored = (baseline, list(analysis.findings), parse_map)
            # Sync legacy store for backward compat
            _baseline_store[repo_key] = stored

        baseline, baseline_findings, baseline_parse_map = stored

        # -- Parse only files that are changed vs baseline snapshot ----------
        # A file can stay in ``git diff`` for a long time. If its current
        # content hash already matches the baseline snapshot, re-parsing it
        # on every nudge call is pure overhead and does not improve quality.
        from drift.cache import ParseCache

        current_parse: dict[str, ParseResult] = {}
        effective_changed_set: set[str] = set()
        unchanged_hash_skips = 0

        # Resolve language + exclude checks for changed files directly
        # instead of walking the entire file tree via discover_files().
        # Nudge typically touches 1-5 files, so per-file checks are
        # significantly cheaper than a full glob walk.
        from drift.ingestion.file_discovery import (
            _matches_any_prepared,
            _prepare_patterns,
            detect_language,
        )

        exclude_patterns = cfg.exclude or [
            "**/node_modules/**", "**/__pycache__/**", "**/venv/**",
            "**/.venv/**", "**/.git/**", "**/dist/**", "**/build/**",
            "**/site-packages/**", "**/tests/**", "**/scripts/**",
        ]
        prepared_exclude = _prepare_patterns(tuple(exclude_patterns))

        for fp in changed_set:
            full_path = repo_path / fp

            # Quick exclude/language check instead of full tree walk
            if _matches_any_prepared(fp, prepared_exclude):
                continue
            if not full_path.is_file():
                record_parse_failure(
                    file_path=fp,
                    stage="changed",
                    reason="file_not_discovered",
                    errors=["changed file is not part of discoverable source set"],
                )
                # Keep this in the changed set for conservative downstream handling.
                effective_changed_set.add(fp)
                continue

            lang = detect_language(full_path)
            if lang is None:
                # Unsupported file type — skip silently
                continue

            try:
                current_hash = ParseCache.file_hash(full_path)
            except OSError:
                current_hash = None

            baseline_hash = baseline.file_hashes.get(fp)
            baseline_parse_result = baseline_parse_map.get(fp)
            baseline_has_parse_errors = bool(
                baseline_parse_result and baseline_parse_result.parse_errors
            )
            if (
                current_hash is not None
                and baseline_hash == current_hash
                and not baseline_has_parse_errors
            ):
                unchanged_hash_skips += 1
                continue

            effective_changed_set.add(fp)
            try:
                pr = parse_file(Path(fp), repo_path, lang)
                current_parse[fp] = pr
                if pr.parse_errors:
                    record_parse_failure(
                        file_path=fp,
                        stage="changed",
                        reason="parse_errors",
                        errors=pr.parse_errors,
                    )
            except Exception as exc:
                record_parse_failure(
                    file_path=fp,
                    stage="changed",
                    reason="parse_exception",
                    errors=[str(exc)],
                )
                continue

        # De-duplicate for deterministic response contracts.
        parse_failed_files = sorted(
            {
                (
                    e["file"],
                    e["stage"],
                    e["reason"],
                    tuple(e.get("errors", [])),
                ): e
                for e in parse_failed_files
            }.values(),
            key=lambda e: (e["stage"], e["file"], e["reason"]),
        )
        parse_failure_count = len(parse_failed_files)

        # -- Run incremental analysis ---------------------------------------
        # Fast path: no effective source-file changes means no directional
        # signal delta; avoid invoking the full incremental runner.
        if not effective_changed_set and parse_failure_count == 0:
            from drift.incremental import IncrementalResult

            inc_result = IncrementalResult(
                direction="stable",
                delta=0.0,
                score=baseline.score,
                new_findings=[],
                resolved_findings=[],
                confidence={},
                file_local_signals_run=[],
                cross_file_signals_estimated=[],
                baseline_valid=True,
            )
        else:
            runner = IncrementalSignalRunner(
                baseline=baseline,
                config=cfg,
                baseline_findings=baseline_findings,
                baseline_parse_results=baseline_parse_map,
            )
            inc_result = runner.run(effective_changed_set, current_parse)

        # -- safe_to_commit hardrule (Step 13) ------------------------------
        blocking_reasons: list[str] = []

        # Rule (e): git detection failed — empty file-set is unreliable
        if git_detection_failed and not changed_set:
            blocking_reasons.append(
                "Git change detection failed; "
                "pass changed_files explicitly or check git availability"
            )

        # Rule (a): new findings with critical/high severity
        for f in inc_result.new_findings:
            if f.severity.value in ("critical", "high"):
                blocking_reasons.append(
                    f"New {f.severity.value} finding: {f.title}"
                )
                break  # one reason suffices

        # Rule (b): significant degradation
        if inc_result.delta > _NUDGE_SIGNIFICANT_DELTA:
            blocking_reasons.append(
                f"Score degradation of {inc_result.delta:+.4f} exceeds threshold"
            )

        # Rule (c): expired baseline
        if not inc_result.baseline_valid:
            blocking_reasons.append("Baseline expired — full rescan recommended")

        # Rule (d): parse failures hide analyzable surface and therefore block commit safety.
        if parse_failure_count > 0:
            blocking_reasons.append(
                f"Parse failures in {parse_failure_count} file(s): "
                "affected files were skipped or only partially analyzable"
            )

        safe_to_commit = len(blocking_reasons) == 0

        # -- Magnitude label -----------------------------------------------
        abs_delta = abs(inc_result.delta)
        if abs_delta < 0.01:
            magnitude = "minor"
        elif abs_delta < 0.05:
            magnitude = "moderate"
        else:
            magnitude = "significant"

        # -- Nudge message --------------------------------------------------
        if inc_result.direction == "improving":
            nudge_msg = "Changes improve architectural coherence. Safe to proceed."
        elif inc_result.direction == "stable":
            nudge_msg = "No measurable drift impact. Continue."
        elif safe_to_commit:
            nudge_msg = (
                "Minor degradation detected but within acceptable bounds. "
                "Consider reviewing before committing."
            )
        else:
            nudge_msg = (
                "Significant drift detected. Review the blocking reasons "
                "before committing."
            )

        # -- Build response -------------------------------------------------
        # Apply signal filtering to new/resolved findings if requested
        _new = inc_result.new_findings
        _resolved = inc_result.resolved_findings
        if signals or exclude_signals:
            _include = {s.upper() for s in signals} if signals else None
            _exclude = {s.upper() for s in exclude_signals} if exclude_signals else set()
            def _sig_match(f: Finding) -> bool:
                abbr = signal_abbrev(f.signal_type)
                if _include is not None and abbr not in _include:
                    return False
                return abbr not in _exclude
            _new = [f for f in _new if _sig_match(f)]
            _resolved = [f for f in _resolved if _sig_match(f)]

        result = _base_response(
            direction=inc_result.direction,
            delta=inc_result.delta,
            magnitude=magnitude,
            score=round(inc_result.score, 4),
            safe_to_commit=safe_to_commit,
            blocking_reasons=blocking_reasons,
            nudge=nudge_msg,
            new_findings=[_finding_concise(f) for f in _new[:5]],
            resolved_findings=[
                _finding_concise(f) for f in _resolved[:5]
            ],
            confidence=inc_result.confidence,
            expected_transient=False,  # MVP: always false (Step 14)
            baseline_age_seconds=round(
                _time.time() - baseline.created_at, 1
            ),
            baseline_valid=inc_result.baseline_valid,
            baseline_refresh_reason=baseline_refresh_reason,
            file_local_signals_run=inc_result.file_local_signals_run,
            cross_file_signals_estimated=inc_result.cross_file_signals_estimated,
            parse_failure_count=parse_failure_count,
            parse_failed_files=parse_failed_files,
            parse_failure_treatment={
                "affects_safe_to_commit": True,
                "policy": "blocking",
                "condition": "parse_failure_count > 0",
                "explanation": (
                    "Nudge marks safe_to_commit as false when parse failures are present "
                    "because impacted files were not fully analyzable."
                ),
            },
            changed_files=sorted(changed_set),
            ignored_changed_files=ignored_changed_files,
            analyzed_changed_files=sorted(effective_changed_set),
            unchanged_hash_skips=unchanged_hash_skips,
            agent_instruction=(
                "Use drift_nudge between edits for fast direction checks. "
                "If safe_to_commit is false, address blocking_reasons first. "
                "Call drift_diff after completing a batch for full verification."
            ),
        )
        result.update(_nudge_next_step_contract(safe_to_commit=safe_to_commit))

        _emit_api_telemetry(
            tool_name="api.nudge",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return shape_for_profile(result, response_profile)

    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.nudge",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response("DRIFT-5001", str(exc), recoverable=True)


def invalidate_nudge_baseline(path: str | Path = ".") -> None:
    """Force a fresh baseline on the next nudge call for *path*."""
    from drift.incremental import BaselineManager

    repo_path = Path(path).resolve()
    repo_key = repo_path.as_posix()
    # Invalidate both BaselineManager and legacy store
    BaselineManager.instance().invalidate(repo_path)
    _baseline_store.pop(repo_key, None)
