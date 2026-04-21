"""Nudge endpoint — incremental directional feedback after file changes."""

from __future__ import annotations

from dataclasses import dataclass
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
    apply_output_mode,
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


@dataclass(frozen=True)
class _NudgeBlockingState:
    """Typed outcome of safe-to-commit gate evaluation."""

    safe_to_commit: bool
    blocking_reasons: list[str]


def _build_nudge_blocking_state(
    *,
    inc_result: Any,
    git_detection_failed: bool,
    changed_set_empty: bool,
    parse_failure_count: int,
    significant_delta_threshold: float,
) -> _NudgeBlockingState:
    """Derive safe_to_commit and blocking reasons from incremental state."""
    blocking_reasons: list[str] = []

    if git_detection_failed and changed_set_empty:
        blocking_reasons.append(
            "Git change detection failed; "
            "pass changed_files explicitly or check git availability"
        )

    for finding in inc_result.new_findings:
        if finding.severity.value in ("critical", "high"):
            blocking_reasons.append(
                f"New {finding.severity.value} finding: {finding.title}"
            )
            break

    if inc_result.delta > significant_delta_threshold:
        blocking_reasons.append(
            f"Score degradation of {inc_result.delta:+.4f} exceeds threshold"
        )

    if not inc_result.baseline_valid:
        blocking_reasons.append("Baseline expired — full rescan recommended")

    if parse_failure_count > 0:
        blocking_reasons.append(
            f"Parse failures in {parse_failure_count} file(s): "
            "affected files were skipped or only partially analyzable"
        )

    return _NudgeBlockingState(
        safe_to_commit=len(blocking_reasons) == 0,
        blocking_reasons=blocking_reasons,
    )


def _nudge_magnitude_label(delta: float) -> str:
    """Return magnitude bucket for a score delta."""
    abs_delta = abs(delta)
    if abs_delta < 0.01:
        return "minor"
    if abs_delta < 0.05:
        return "moderate"
    return "significant"


def _cross_file_blind_spot_warning(
    cross_file_signals_estimated: list[str],
) -> dict[str, Any] | None:
    """Return a warning payload when incremental mode reuses cross-file baseline signals."""
    if not cross_file_signals_estimated:
        return None

    signals = sorted({signal_abbrev(sig) for sig in cross_file_signals_estimated})
    signal_list = ", ".join(signals)
    return {
        "code": "cross_file_blind_spot",
        "signals": signals,
        "message": (
            f"Cross-file signals ({signal_list}) reflect baseline state only. "
            "Run drift analyze to detect newly introduced cross-file problems."
        ),
    }


def _removed_file_prune_warning(pruned_count: int) -> dict[str, Any] | None:
    """Return a warning payload when stale findings were pruned for removed files."""
    if pruned_count <= 0:
        return None
    noun = "finding" if pruned_count == 1 else "findings"
    return {
        "code": "removed_file_findings_pruned",
        "count": pruned_count,
        "message": (
            f"{pruned_count} {noun} from removed files were pruned from "
            "cross-file signal results."
        ),
    }


class _NudgeExecution:
    """Command object that encapsulates a single nudge() call.

    Splits the execution into focused phase methods so every method stays
    below the CXS threshold of 15.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        changed_files: list[str] | None,
        uncommitted: bool,
        signals: list[str] | None,
        exclude_signals: list[str] | None,
        response_profile: str | None,
        task_signal: str | None,
        task_edit_kind: str | None,
        task_context_class: str | None,
        timeout_ms: int | None = 1000,
    ) -> None:
        import time as _time

        self._time = _time
        self._start_ms = _time.monotonic()
        self.repo_path = Path(path).resolve()
        self.repo_key = self.repo_path.as_posix()
        self.params: dict[str, Any] = {
            "path": str(path),
            "changed_files": changed_files,
            "uncommitted": uncommitted,
        }
        self._initial_changed_files = changed_files
        self.uncommitted = uncommitted
        self.timeout_ms = timeout_ms
        self.signals = signals
        self.exclude_signals = exclude_signals
        self.response_profile = response_profile
        self.task_signal = task_signal
        self.task_edit_kind = task_edit_kind
        self.task_context_class = task_context_class
        self.parse_failed_files: list[dict[str, Any]] = []

        # Set during execution phases
        self.cfg: Any = None
        self.changed_set: set[str] = set()
        self.ignored_changed_files: list[str] = []
        self.git_detection_failed: bool = False
        self.baseline: Any = None
        self.baseline_findings: list[Any] = []
        self.baseline_parse_map: dict[str, Any] = {}
        self.baseline_refresh_reason: str | None = None
        self.current_parse: dict[str, Any] = {}
        self.effective_changed_set: set[str] = set()
        self.unchanged_hash_skips: int = 0
        self.inc_result: Any = None

    def elapsed_ms(self) -> int:
        return int((self._time.monotonic() - self._start_ms) * 1_000)

    def _record_parse_failure(
        self,
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
        self.parse_failed_files.append(entry)

    def _load_config(self) -> None:
        self.cfg = _load_config_cached(self.repo_path)
        _warn_config_issues(self.cfg)

    def _detect_changed_files(self) -> None:
        changed_files = self._initial_changed_files
        self.git_detection_failed = False
        if changed_files is None:
            detected = _get_changed_files_from_git(
                self.repo_path, uncommitted=self.uncommitted
            )
            if detected is None:
                self.git_detection_failed = True
                changed_files = []
            else:
                changed_files = detected
        self.changed_set = set(changed_files)
        self.ignored_changed_files = sorted(
            fp for fp in self.changed_set if _is_derived_cache_artifact(fp)
        )
        if self.ignored_changed_files:
            self.changed_set.difference_update(self.ignored_changed_files)

    def _ensure_baseline(self) -> None:
        from drift.incremental import BaselineManager

        cfg = self.cfg
        mgr = BaselineManager.instance()
        stored = mgr.get(self.repo_path, config=cfg)
        self.baseline_refresh_reason = None
        if stored is not None:
            self.baseline_refresh_reason = mgr.consume_refresh_reason(self.repo_path)

        if stored is None:
            stored = self._create_baseline(mgr)

        self.baseline, self.baseline_findings, self.baseline_parse_map = stored

    def _create_baseline(self, mgr: Any) -> Any:
        from drift.analyzer import analyze_repo
        from drift.cache import ParseCache
        from drift.incremental import BaselineSnapshot
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files

        cfg = self.cfg
        self.baseline_refresh_reason = (
            mgr.consume_refresh_reason(self.repo_path) or "baseline_missing"
        )
        all_files = discover_files(
            self.repo_path,
            include=cfg.include,
            exclude=cfg.exclude,
            max_files=cfg.thresholds.max_discovery_files,
            cache_dir=cfg.cache_dir,
        )
        analysis = analyze_repo(self.repo_path, config=cfg)

        pcache = ParseCache(self.repo_path / cfg.cache_dir)
        file_hashes: dict[str, str] = {}
        parse_map: dict[str, Any] = {}
        for finfo in all_files:
            full_path = self.repo_path / finfo.path
            posix = finfo.path.as_posix()
            try:
                h = ParseCache.file_hash(full_path)
                file_hashes[posix] = h
            except OSError:
                continue

            cached_pr = pcache.get(h)
            if cached_pr is not None:
                if cached_pr.file_path != finfo.path:
                    cached_pr.file_path = finfo.path
                parse_map[posix] = cached_pr
                continue

            try:
                pr = parse_file(finfo.path, self.repo_path, finfo.language)
                parse_map[posix] = pr
                if pr.parse_errors:
                    self._record_parse_failure(
                        file_path=posix,
                        stage="baseline",
                        reason="parse_errors",
                        errors=pr.parse_errors,
                    )
            except Exception as exc:
                self._record_parse_failure(
                    file_path=posix,
                    stage="baseline",
                    reason="parse_exception",
                    errors=[str(exc)],
                )

        baseline = BaselineSnapshot(
            file_hashes=file_hashes,
            score=analysis.drift_score,
            ttl_seconds=cfg.nudge_baseline_ttl_seconds,
        )
        mgr.store(
            self.repo_path,
            baseline,
            list(analysis.findings),
            parse_map,
            config=cfg,
        )
        stored = (baseline, list(analysis.findings), parse_map)
        # Sync legacy store for backward compat
        _baseline_store[self.repo_key] = stored
        return stored

    def _parse_changed_files(self) -> None:
        from drift.cache import ParseCache
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import (
            _matches_any_prepared,
            _prepare_patterns,
            detect_language,
        )

        cfg = self.cfg
        exclude_patterns = cfg.exclude or [
            "**/node_modules/**", "**/__pycache__/**", "**/venv/**",
            "**/.venv/**", "**/.git/**", "**/dist/**", "**/build/**",
            "**/site-packages/**", "**/tests/**", "**/scripts/**",
        ]
        prepared_exclude = _prepare_patterns(tuple(exclude_patterns))

        for fp in self.changed_set:
            self._parse_single_changed_file(
                fp, prepared_exclude, ParseCache, parse_file, detect_language,
                _matches_any_prepared,
            )

        # De-duplicate for deterministic response contracts.
        self.parse_failed_files = sorted(
            {
                (
                    e["file"],
                    e["stage"],
                    e["reason"],
                    tuple(e.get("errors", [])),
                ): e
                for e in self.parse_failed_files
            }.values(),
            key=lambda e: (e["stage"], e["file"], e["reason"]),
        )

    def _parse_single_changed_file(
        self,
        fp: str,
        prepared_exclude: Any,
        parse_cache_cls: Any,
        parse_file: Any,
        detect_language: Any,
        matches_any: Any,
    ) -> None:
        full_path = self.repo_path / fp
        if matches_any(fp, prepared_exclude):
            return
        if not full_path.is_file():
            self._record_parse_failure(
                file_path=fp,
                stage="changed",
                reason="file_not_discovered",
                errors=["changed file is not part of discoverable source set"],
            )
            self.effective_changed_set.add(fp)
            return

        lang = detect_language(full_path)
        if lang is None:
            return

        try:
            current_hash = parse_cache_cls.file_hash(full_path)
        except OSError:
            current_hash = None

        baseline_parse_result = self.baseline_parse_map.get(fp)
        baseline_has_parse_errors = bool(
            baseline_parse_result and baseline_parse_result.parse_errors
        )
        if (
            current_hash is not None
            and self.baseline.file_hashes.get(fp) == current_hash
            and not baseline_has_parse_errors
        ):
            self.unchanged_hash_skips += 1
            return

        self.effective_changed_set.add(fp)
        try:
            pr = parse_file(Path(fp), self.repo_path, lang)
            self.current_parse[fp] = pr
            if pr.parse_errors:
                self._record_parse_failure(
                    file_path=fp,
                    stage="changed",
                    reason="parse_errors",
                    errors=pr.parse_errors,
                )
        except Exception as exc:
            self._record_parse_failure(
                file_path=fp,
                stage="changed",
                reason="parse_exception",
                errors=[str(exc)],
            )

    def _run_incremental_analysis(self) -> None:
        from drift.incremental import IncrementalResult, IncrementalSignalRunner

        parse_failure_count = len(self.parse_failed_files)
        if not self.effective_changed_set and parse_failure_count == 0:
            self.inc_result = IncrementalResult(
                direction="stable",
                delta=0.0,
                score=self.baseline.score,
                new_findings=[],
                resolved_findings=[],
                confidence={},
                file_local_signals_run=[],
                cross_file_signals_estimated=[],
                baseline_valid=True,
            )
            return

        runner = IncrementalSignalRunner(
            baseline=self.baseline,
            config=self.cfg,
            baseline_findings=self.baseline_findings,
            baseline_parse_results=self.baseline_parse_map,
            repo_path=self.repo_path,
        )
        self.inc_result = runner.run(self.effective_changed_set, self.current_parse)

    def _filter_findings(self) -> tuple[list[Any], list[Any]]:
        from drift.models import Finding  # noqa: F401 — used via type narrowing

        _new = self.inc_result.new_findings
        _resolved = self.inc_result.resolved_findings
        if not (self.signals or self.exclude_signals):
            return _new, _resolved

        _include = {s.upper() for s in self.signals} if self.signals else None
        _exclude = {s.upper() for s in self.exclude_signals} if self.exclude_signals else set()

        def _sig_match(f: Any) -> bool:
            abbr = signal_abbrev(f.signal_type)
            if _include is not None and abbr not in _include:
                return False
            return abbr not in _exclude

        return [f for f in _new if _sig_match(f)], [f for f in _resolved if _sig_match(f)]

    def _build_nudge_message(
        self, *, safe_to_commit: bool
    ) -> str:
        direction = self.inc_result.direction
        if direction == "improving":
            return "Changes improve architectural coherence. Safe to proceed."
        if direction == "stable":
            return "No measurable drift impact. Continue."
        if safe_to_commit:
            return (
                "Minor degradation detected but within acceptable bounds. "
                "Consider reviewing before committing."
            )
        return (
            "Significant drift detected. Review the blocking reasons "
            "before committing."
        )

    def _collect_warnings(self) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        blind_spot = _cross_file_blind_spot_warning(
            self.inc_result.cross_file_signals_estimated
        )
        if blind_spot is not None:
            warnings.append(blind_spot)
        prune = _removed_file_prune_warning(
            self.inc_result.pruned_removed_cross_file_findings
        )
        if prune is not None:
            warnings.append(prune)
        return warnings

    def _build_response(self) -> dict[str, Any]:
        parse_failure_count = len(self.parse_failed_files)
        blocking_state = _build_nudge_blocking_state(
            inc_result=self.inc_result,
            git_detection_failed=self.git_detection_failed,
            changed_set_empty=not self.changed_set,
            parse_failure_count=parse_failure_count,
            significant_delta_threshold=_NUDGE_SIGNIFICANT_DELTA,
        )
        safe_to_commit = blocking_state.safe_to_commit
        magnitude = _nudge_magnitude_label(self.inc_result.delta)
        nudge_msg = self._build_nudge_message(safe_to_commit=safe_to_commit)
        warnings = self._collect_warnings()
        _new, _resolved = self._filter_findings()

        # --- Bruchstelle 2: Finding cluster summary ---
        cluster_by_signal: dict[str, int] = {}
        for f in _new:
            abbr = signal_abbrev(f.signal_type)
            cluster_by_signal[abbr] = cluster_by_signal.get(abbr, 0) + 1
        finding_cluster_summary = {
            "total_new": len(_new),
            "by_signal": cluster_by_signal,
        }

        # --- Bruchstelle 1: Dynamic agent_instruction ---
        _new_count = len(_new)
        _degrading_signals = sorted(
            {signal_abbrev(f.signal_type) for f in _new}
        ) if _new else []
        # Revert is recommended whenever the commit is unsafe AND at least one
        # hard structural/observability signal is tripped.  This covers:
        #   - direct degradation (direction == "degrading")
        #   - parse failures (file not analyzable -> safe_to_commit==False is
        #     otherwise "soft"; recommend revert so the agent addresses the
        #     syntactic regression first)
        #   - git detection failure with no explicit changed_files (nudge was
        #     blind; the edit could still be regressing undetected)
        _revert_recommended = (not safe_to_commit) and (
            self.inc_result.direction == "degrading"
            or parse_failure_count > 0
            or (self.git_detection_failed and not self.changed_set)
        )
        _latency_ms = self.elapsed_ms()
        _latency_exceeded = (
            self.timeout_ms is not None and _latency_ms > self.timeout_ms
        )
        _auto_fast_path = (
            not self.inc_result.cross_file_signals_estimated
            and bool(self.inc_result.file_local_signals_run)
        )
        # Phase E3: gentle push toward drift_diff when cross-file signals
        # are estimated (not measured) and nothing looks degrading.  Helps
        # catch MDS/AVS regressions that nudge cannot see.
        _cross_file_hint: str | None = None
        if (
            not _auto_fast_path
            and self.inc_result.direction != "degrading"
            and self.inc_result.cross_file_signals_estimated
        ):
            _cross_file_hint = (
                "Cross-file signals are estimated from baseline. "
                "Run drift_diff to verify cross-file impact (MDS/AVS)."
            )
        if _revert_recommended:
            if self.inc_result.direction == "degrading":
                _sig_label = (
                    f" ({', '.join(_degrading_signals)})" if _degrading_signals else ""
                )
                agent_instruction = (
                    f"REVERT this edit immediately. "
                    f"Degradation detected: {_new_count} new finding"
                    f"{'s' if _new_count != 1 else ''}{_sig_label}. "
                    "Address blocking_reasons or run drift_brief for guided repair, "
                    "then try a different approach."
                )
            elif parse_failure_count > 0:
                agent_instruction = (
                    "REVERT this edit: parse failures detected in "
                    f"{parse_failure_count} file(s). Fix syntax/parse errors "
                    "before retrying."
                )
            else:
                agent_instruction = (
                    "REVERT or pass changed_files explicitly. Git change detection "
                    "failed; nudge could not verify this edit."
                )
        elif safe_to_commit:
            agent_instruction = (
                "Use drift_nudge between edits for fast direction checks. "
                "Call drift_diff after completing a batch for full verification."
            )
        else:
            agent_instruction = (
                "Use drift_nudge between edits for fast direction checks. "
                "If safe_to_commit is false, address blocking_reasons first. "
                "Call drift_diff after completing a batch for full verification."
            )

        result = _base_response(
            direction=self.inc_result.direction,
            delta=self.inc_result.delta,
            magnitude=magnitude,
            score=round(self.inc_result.score, 4),
            safe_to_commit=safe_to_commit,
            blocking_reasons=blocking_state.blocking_reasons,
            nudge=nudge_msg,
            new_findings=[_finding_concise(f) for f in _new[:5]],
            resolved_findings=[_finding_concise(f) for f in _resolved[:5]],
            confidence=self.inc_result.confidence,
            expected_transient=False,  # MVP: always false (Step 14)
            baseline_age_seconds=round(
                self._time.time() - self.baseline.created_at, 1
            ),
            baseline_valid=self.inc_result.baseline_valid,
            baseline_refresh_reason=self.baseline_refresh_reason,
            file_local_signals_run=self.inc_result.file_local_signals_run,
            cross_file_signals_estimated=self.inc_result.cross_file_signals_estimated,
            parse_failure_count=parse_failure_count,
            parse_failed_files=self.parse_failed_files,
            parse_failure_treatment={
                "affects_safe_to_commit": True,
                "policy": "blocking",
                "condition": "parse_failure_count > 0",
                "explanation": (
                    "Nudge marks safe_to_commit as false when parse failures are present "
                    "because impacted files were not fully analyzable."
                ),
            },
            changed_files=sorted(self.changed_set),
            ignored_changed_files=self.ignored_changed_files,
            analyzed_changed_files=sorted(self.effective_changed_set),
            unchanged_hash_skips=self.unchanged_hash_skips,
            warnings=warnings,
            finding_cluster_summary=finding_cluster_summary,
            agent_instruction=agent_instruction,
            revert_recommended=_revert_recommended,
            latency_ms=_latency_ms,
            latency_exceeded=_latency_exceeded,
            auto_fast_path=_auto_fast_path,
            cross_file_hint=_cross_file_hint,
        )
        result.update(_nudge_next_step_contract(safe_to_commit=safe_to_commit))
        return result

    def _record_outcome(self) -> None:
        if not (
            self.task_signal
            and self.task_edit_kind
            and self.inc_result.direction in ("improving", "regressing")
        ):
            return
        try:
            from drift.repair_template_registry import get_registry as _get_reg
            _get_reg().record_outcome(
                signal=self.task_signal,
                edit_kind=self.task_edit_kind,
                context_class=self.task_context_class or "production",
                direction=self.inc_result.direction,
                score_delta=self.inc_result.delta,
            )
        except Exception:  # pragma: no cover
            pass  # registry failures must never break nudge

    def _emit_telemetry(
        self, *, status: str, result: dict[str, Any] | None, error: Exception | None
    ) -> None:
        _emit_api_telemetry(
            tool_name="api.nudge",
            params=self.params,
            status=status,
            elapsed_ms=self.elapsed_ms(),
            result=result,
            error=error,
            repo_root=self.repo_path,
        )

    def _execute(self) -> dict[str, Any]:
        self._load_config()
        self._detect_changed_files()
        self._ensure_baseline()
        self._parse_changed_files()
        self._run_incremental_analysis()
        self._record_outcome()
        result = self._build_response()
        self._persist_nudge_state(result)
        result = apply_output_mode(result, getattr(self.cfg, "output_mode", "full"))
        return shape_for_profile(result, self.response_profile)

    def _persist_nudge_state(self, result: dict[str, Any]) -> None:
        """Persist last-nudge state so the pre-commit gate can enforce REVERT.

        Writes ``.drift-cache/last_nudge.json`` with a minimal payload.
        Any failure is silently ignored — nudge must never break the caller.
        """
        try:
            import hashlib
            import json

            cache_dir = self.repo_path / getattr(self.cfg, "cache_dir", ".drift-cache")
            cache_dir.mkdir(parents=True, exist_ok=True)

            # file_hashes for changed files (short sha256) — the gate compares
            # these against staged files to know whether the REVERTed state
            # is still unchanged.
            file_hashes: dict[str, str] = {}
            for fp in sorted(self.changed_set):
                full = self.repo_path / fp
                if full.is_file():
                    try:
                        file_hashes[fp] = hashlib.sha256(
                            full.read_bytes()
                        ).hexdigest()[:16]
                    except OSError:
                        continue

            payload = {
                "schema_version": 1,
                "timestamp": self._time.time(),
                "repo_path": self.repo_path.as_posix(),
                "changed_files": sorted(self.changed_set),
                "file_hashes": file_hashes,
                "revert_recommended": bool(result.get("revert_recommended")),
                "safe_to_commit": bool(result.get("safe_to_commit")),
                "direction": result.get("direction"),
                "delta": result.get("delta"),
                "latency_ms": result.get("latency_ms"),
                "agent_instruction": result.get("agent_instruction"),
            }
            (cache_dir / "last_nudge.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:  # pragma: no cover — persistence is best-effort
            _log.debug("Could not persist last_nudge state", exc_info=True)


    def run(self) -> dict[str, Any]:
        try:
            result = self._execute()
            self._emit_telemetry(status="ok", result=result, error=None)
            return result
        except Exception as exc:
            self._emit_telemetry(status="error", result=None, error=exc)
            return _error_response("DRIFT-5001", str(exc), recoverable=True)


def nudge(
    path: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    uncommitted: bool = True,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
    task_signal: str | None = None,
    task_edit_kind: str | None = None,
    task_context_class: str | None = None,
    timeout_ms: int | None = 1000,
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
    task_signal:
        Signal type of the repair task being verified (e.g. ``"mutant_duplicate"``).
        When set together with *task_edit_kind*, this outcome is recorded in
        the repair template registry for template-confidence learning.
    task_edit_kind:
        Edit kind applied in the repair (e.g. ``"merge_function_body"``).
        Must also set *task_signal* to trigger outcome recording.
    task_context_class:
        Context class for registry lookup (e.g. ``"production"`` or ``"test"``).
        Defaults to ``"production"`` when *task_signal* and *task_edit_kind*
        are set but *task_context_class* is omitted.

    Returns
    -------
    dict
        Nudge response with direction, delta, safe_to_commit, confidence map,
        new/resolved findings, and agent instruction.

    Performance
    -----------
    The **first call** for a repository performs a full scan to establish a
    baseline (typically 2–10 s depending on repo size).  Subsequent calls are
    incremental and usually complete in 0.1–0.5 s.  Callers should expect
    the warm-up cost on the initial invocation.

    Parameters (additional)
    -----------------------
    timeout_ms:
        Total wall-clock budget in milliseconds for this call.  When the
        actual latency exceeds this value the response includes
        ``latency_exceeded: true`` so agents can decide to skip future
        nudge calls.  No early abort is performed; a full result is always
        returned.  Defaults to ``1000`` ms.  Set to ``None`` to disable.
    """
    return _NudgeExecution(
        path,
        changed_files=changed_files,
        uncommitted=uncommitted,
        signals=signals,
        exclude_signals=exclude_signals,
        response_profile=response_profile,
        task_signal=task_signal,
        task_edit_kind=task_edit_kind,
        task_context_class=task_context_class,
        timeout_ms=timeout_ms,
    ).run()


def invalidate_nudge_baseline(path: str | Path = ".") -> None:
    """Force a fresh baseline on the next nudge call for *path*."""
    from drift.incremental import BaselineManager

    repo_path = Path(path).resolve()
    repo_key = repo_path.as_posix()
    # Invalidate both BaselineManager and legacy store
    BaselineManager.instance().invalidate(repo_path)
    _baseline_store.pop(repo_key, None)
