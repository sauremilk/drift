"""Incremental analysis foundation for Drift.

Provides:

* ``BaselineSnapshot`` — lightweight checkpoint of analysis state.
* ``IncrementalResult`` — outcome of an incremental signal run.
* ``IncrementalSignalRunner`` — runs only the signals affected by file changes.
* ``BaselineManager`` — singleton that manages baselines with git-event detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from drift import __version__

if TYPE_CHECKING:
    from drift.config import DriftConfig
    from drift.models import Finding, ParseResult

logger = logging.getLogger("drift")


@dataclass(slots=True)
class BaselineSnapshot:
    """Immutable snapshot of file hashes captured after a full scan.

    The snapshot tracks which files existed and their content hashes so
    that a subsequent incremental run can determine the minimal set of
    files that actually changed.

    Parameters
    ----------
    file_hashes:
        Mapping of ``file_path`` (posix string) → content SHA-256 prefix
        as produced by ``ParseCache.file_hash``.
    score:
        Composite drift score at the time the baseline was captured.
    created_at:
        Unix timestamp of snapshot creation (defaults to ``time.time()``).
    ttl_seconds:
        Time-to-live in seconds.  ``is_valid()`` returns ``False`` after
        this period to force a full re-scan.
    """

    file_hashes: dict[str, str]
    score: float = 0.0
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 900  # 15 minutes

    # -- queries -------------------------------------------------------------

    def is_valid(self) -> bool:
        """Return ``True`` if the snapshot has not expired."""
        return (time.time() - self.created_at) < self.ttl_seconds

    def changed_files(
        self,
        current_hashes: dict[str, str],
    ) -> tuple[set[str], set[str], set[str]]:
        """Compare *current_hashes* against the baseline.

        Returns
        -------
        (added, removed, modified)
            Three disjoint sets of file paths (posix strings).
        """
        baseline_keys = set(self.file_hashes)
        current_keys = set(current_hashes)

        added = current_keys - baseline_keys
        removed = baseline_keys - current_keys
        modified = {
            p for p in baseline_keys & current_keys if self.file_hashes[p] != current_hashes[p]
        }
        return added, removed, modified

    def all_changed(self, current_hashes: dict[str, str]) -> set[str]:
        """Return the union of added, removed, and modified file paths."""
        added, removed, modified = self.changed_files(current_hashes)
        return added | removed | modified


# ---------------------------------------------------------------------------
# Incremental result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class IncrementalResult:
    """Outcome of an incremental signal run against a baseline.

    Attributes
    ----------
    score:
        Composite drift score computed from the merged findings.
    delta:
        ``score - baseline.score``.  Negative means improving.
    direction:
        Human-readable trend label.
    new_findings:
        Findings present now but absent in the baseline.
    resolved_findings:
        Findings present in the baseline but absent now.
    confidence:
        Per-signal confidence level.  ``"exact"`` for file-local signals
        run only on changed files; ``"estimated"`` for cross-file / git
        signals whose baseline findings were carried forward.
    file_local_signals_run:
        Signal types that ran on the changed files with exact precision.
    cross_file_signals_estimated:
        Signal types whose findings were carried from the baseline.
    baseline_valid:
        Whether the baseline TTL had not expired when the run started.
    pruned_removed_cross_file_findings:
        Number of carried cross-file baseline findings dropped because
        their file path no longer exists in the current parse set.
    """

    score: float
    delta: float
    direction: Literal["improving", "stable", "degrading"]
    new_findings: list[Finding]
    resolved_findings: list[Finding]
    confidence: dict[str, Literal["exact", "estimated"]]
    file_local_signals_run: list[str]
    cross_file_signals_estimated: list[str]
    baseline_valid: bool
    pruned_removed_cross_file_findings: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DELTA_THRESHOLD = 0.005  # score change below this is "stable"


def _direction_for_delta(delta: float) -> Literal["improving", "stable", "degrading"]:
    if delta < -_DELTA_THRESHOLD:
        return "improving"
    if delta > _DELTA_THRESHOLD:
        return "degrading"
    return "stable"


def _finding_key(f: Finding) -> str:
    """Deterministic identity key for a finding (signal + file + location)."""
    fp = f.file_path.as_posix() if f.file_path else ""
    return f"{f.signal_type}::{fp}::{f.start_line}::{f.title}"


# ---------------------------------------------------------------------------
# Git state tracking (Phase 5 — Step 19)
# ---------------------------------------------------------------------------

_MAX_CHANGED_FILES_BEFORE_INVALIDATION = 10
_NUDGE_BASELINE_SCHEMA_VERSION = 1

# Short TTL cache for _capture_git_state to avoid spawning 3 subprocesses
# per BaselineManager.get() call.  During a nudge loop the git state is
# unlikely to change between consecutive calls separated by < 5 s.
_GIT_STATE_CACHE_LOCK = threading.Lock()
_GIT_STATE_CACHE: dict[str, tuple[float, _GitState | None]] = {}
_GIT_STATE_CACHE_TTL = 5.0


@dataclass(slots=True)
class _GitState:
    """Captures point-in-time git state for change detection."""

    head_commit: str
    stash_hash: str  # hash of ``git stash list`` output
    changed_file_count: int


def _capture_git_state(repo_path: Path) -> _GitState | None:
    """Snapshot current HEAD, stash list, and dirty-file count.

    Returns ``None`` when git is unavailable or the path is not a repo.
    Uses a short TTL cache (5 s) to avoid repeated subprocess spawns
    within rapid-fire nudge loops.
    """
    posix_key = repo_path.resolve().as_posix()
    now = time.monotonic()
    with _GIT_STATE_CACHE_LOCK:
        cached = _GIT_STATE_CACHE.get(posix_key)
        if cached is not None and (now - cached[0]) < _GIT_STATE_CACHE_TTL:
            return cached[1]

    result = _capture_git_state_uncached(repo_path)

    with _GIT_STATE_CACHE_LOCK:
        _GIT_STATE_CACHE[posix_key] = (now, result)
    return result


def _capture_git_state_uncached(repo_path: Path) -> _GitState | None:
    """Perform the actual subprocess calls for git state capture."""
    import hashlib

    def _git(*args: str) -> str | None:
        try:
            proc = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=repo_path,
                check=True,
                stdin=subprocess.DEVNULL,
            )
            return proc.stdout.strip()
        except Exception:
            return None

    head = _git("rev-parse", "HEAD")
    if head is None:
        return None

    stash_raw = _git("stash", "list") or ""
    stash_hash = hashlib.sha256(stash_raw.encode()).hexdigest()[:16]

    diff_raw = _git("diff", "--name-only", "HEAD") or ""
    changed_count = len([line for line in diff_raw.splitlines() if line])

    return _GitState(
        head_commit=head,
        stash_hash=stash_hash,
        changed_file_count=changed_count,
    )


# ---------------------------------------------------------------------------
# BaselineManager singleton (Phase 5 — Step 18)
# ---------------------------------------------------------------------------


class BaselineManager:
    """Per-repo baseline management with automatic git-event invalidation.

    Usage::

        mgr = BaselineManager.instance()
        stored = mgr.get(repo_path)
        if stored is None:
            # create baseline via full scan …
            mgr.store(repo_path, baseline, findings, parse_map)

    The manager automatically invalidates a cached baseline when it
    detects that the git state has changed (branch switch, new commit,
    stash change, or many file changes beyond a threshold).
    """

    _instance: ClassVar[BaselineManager | None] = None

    def __init__(self) -> None:
        self._store: dict[
            str,
            tuple[BaselineSnapshot, list[Finding], dict[str, ParseResult]],
        ] = {}
        self._nudge_key_meta: dict[str, tuple[str, str, str]] = {}
        self._git_state: dict[str, _GitState] = {}
        self._last_refresh_reason: dict[str, str] = {}

    @classmethod
    def instance(cls) -> BaselineManager:
        """Return the module-level singleton (created on first call)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton (for testing only)."""
        cls._instance = None

    # -- public API ----------------------------------------------------------

    def get(
        self,
        repo_path: Path,
        *,
        config: DriftConfig | None = None,
    ) -> tuple[BaselineSnapshot, list[Finding], dict[str, ParseResult]] | None:
        """Return stored baseline or ``None`` if missing / expired / invalidated.

        Performs a git-state check: if HEAD, stash, or changed-file count
        diverged since the baseline was stored, the entry is silently
        invalidated and ``None`` is returned.
        """
        repo_key = repo_path.resolve().as_posix()
        stored = self._store.get(repo_key)
        if stored is None and config is not None:
            loaded = self._load_persisted_nudge_baseline(repo_path, config)
            if loaded is not None:
                self._store[repo_key] = loaded
                stored = loaded
                self._last_refresh_reason[repo_key] = "disk_warm_hit"

        if stored is None:
            self._last_refresh_reason[repo_key] = "baseline_missing"
            return None

        if config is not None:
            current_meta = self._compute_nudge_key_meta(repo_path, config)
            previous_meta = self._nudge_key_meta.get(repo_key)
            if previous_meta is not None and previous_meta != current_meta:
                if previous_meta[0] != current_meta[0]:
                    reason = "git_head_changed"
                elif previous_meta[1] != current_meta[1]:
                    reason = "config_fingerprint_changed"
                else:
                    reason = "baseline_key_changed"
                self._last_refresh_reason[repo_key] = reason
                self.invalidate(repo_path)
                return None

        # TTL expiry
        if not stored[0].is_valid():
            logger.debug("Baseline expired for %s (TTL).", repo_key)
            self._last_refresh_reason[repo_key] = "ttl_expired"
            self.invalidate(repo_path)
            return None

        # Git-event invalidation (Step 19)
        invalidation_reason = self._git_state_changed(repo_path)
        if invalidation_reason is not None:
            logger.info(
                "Git state changed for %s (%s) — invalidating baseline.",
                repo_key,
                invalidation_reason,
            )
            self._last_refresh_reason[repo_key] = invalidation_reason
            self.invalidate(repo_path)
            return None

        return stored

    def store(
        self,
        repo_path: Path,
        baseline: BaselineSnapshot,
        findings: list[Finding],
        parse_map: dict[str, ParseResult],
        *,
        config: DriftConfig | None = None,
    ) -> None:
        """Cache a baseline and snapshot the current git state."""
        repo_key = repo_path.resolve().as_posix()
        self._store[repo_key] = (baseline, findings, parse_map)
        self._last_refresh_reason.pop(repo_key, None)

        if config is not None:
            key_meta = self._compute_nudge_key_meta(repo_path, config)
            self._nudge_key_meta[repo_key] = key_meta
            self._persist_nudge_baseline(
                repo_path=repo_path,
                cache_dir=config.cache_dir,
                key_meta=key_meta,
                baseline=baseline,
                findings=findings,
            )

        git_state = _capture_git_state(repo_path)
        if git_state is not None:
            self._git_state[repo_key] = git_state

    def invalidate(self, repo_path: Path) -> None:
        """Remove cached baseline for *repo_path*."""
        repo_key = repo_path.resolve().as_posix()
        self._store.pop(repo_key, None)
        self._nudge_key_meta.pop(repo_key, None)
        self._git_state.pop(repo_key, None)

    def consume_refresh_reason(self, repo_path: Path) -> str | None:
        """Return and clear the last refresh reason for *repo_path*."""
        repo_key = repo_path.resolve().as_posix()
        return self._last_refresh_reason.pop(repo_key, None)

    def has_baseline(self, repo_path: Path) -> bool:
        """Return ``True`` if a valid baseline is cached (no git check)."""
        repo_key = repo_path.resolve().as_posix()
        stored = self._store.get(repo_key)
        return stored is not None and stored[0].is_valid()

    # -- internal ------------------------------------------------------------

    def _git_state_changed(self, repo_path: Path) -> str | None:
        """Return invalidation reason when git state changed, else ``None``."""
        repo_key = repo_path.resolve().as_posix()
        previous = self._git_state.get(repo_key)
        if previous is None:
            # No git state recorded — cannot detect changes
            return None

        # Bypass the TTL cache on the invalidation path: a HEAD change that
        # occurs within the 5-second window would otherwise be invisible here
        # and cause stale incremental results (issue #372).
        current = _capture_git_state_uncached(repo_path)
        if current is None:
            return None

        # Keep the shared TTL cache consistent with the fresh capture so that
        # non-invalidation callers (e.g. _compute_nudge_key_meta) benefit from
        # the up-to-date state without spawning additional subprocesses.
        with _GIT_STATE_CACHE_LOCK:
            _GIT_STATE_CACHE[repo_key] = (time.monotonic(), current)

        # (a) Branch switch or new commit
        if current.head_commit != previous.head_commit:
            return "git_head_changed"

        # (b) Stash changed
        if current.stash_hash != previous.stash_hash:
            return "stash_changed"

        # (c) Invalidate only when crossing from <= threshold to > threshold.
        # This avoids repeated invalidations in persistently dirty repos where
        # the changed-file count remains high but stable across calls.
        if (
            previous.changed_file_count <= _MAX_CHANGED_FILES_BEFORE_INVALIDATION
            and current.changed_file_count > _MAX_CHANGED_FILES_BEFORE_INVALIDATION
        ):
            return "changed_file_threshold"

        return None

    def _compute_nudge_key_meta(
        self,
        repo_path: Path,
        config: DriftConfig,
    ) -> tuple[str, str, str]:
        """Return key metadata tuple: (head_commit, config_fingerprint, key_hash)."""
        git_state = _capture_git_state(repo_path)
        head_commit = git_state.head_commit if git_state is not None else "nogit"
        cfg_payload = json.dumps(
            config.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        cfg_fingerprint = hashlib.sha256(cfg_payload.encode("utf-8")).hexdigest()[:16]
        raw_key = f"v{_NUDGE_BASELINE_SCHEMA_VERSION}:{head_commit}:{cfg_fingerprint}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
        return head_commit, cfg_fingerprint, key_hash

    def _nudge_baseline_path(
        self,
        repo_path: Path,
        cache_dir: str,
        key_meta: tuple[str, str, str],
    ) -> Path:
        """Return filesystem path for a persistent nudge baseline artifact."""
        key_hash = key_meta[2]
        return repo_path / cache_dir / "nudge_baselines" / f"baseline_{key_hash}.json"

    def _persist_nudge_baseline(
        self,
        *,
        repo_path: Path,
        cache_dir: str,
        key_meta: tuple[str, str, str],
        baseline: BaselineSnapshot,
        findings: list[Finding],
    ) -> None:
        """Persist baseline payload for cross-process warm starts.

        Uses atomic temp-file replacement to avoid partial writes.
        """
        path = self._nudge_baseline_path(repo_path, cache_dir, key_meta)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "schema_version": _NUDGE_BASELINE_SCHEMA_VERSION,
            "drift_version": __version__,
            "head_commit": key_meta[0],
            "config_fingerprint": key_meta[1],
            "created_at": baseline.created_at,
            "ttl_seconds": baseline.ttl_seconds,
            "score": baseline.score,
            "file_hashes": baseline.file_hashes,
            "findings": [self._serialize_finding(f) for f in findings],
        }

        fd, tmp_name = tempfile.mkstemp(
            prefix=".nudge-baseline-",
            suffix=".json",
            dir=path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True)
            Path(tmp_name).replace(path)
        except Exception:
            logger.debug(
                "Failed to persist nudge baseline to %s",
                path,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            with suppress(OSError):
                Path(tmp_name).unlink(missing_ok=True)

    def _load_persisted_nudge_baseline(
        self,
        repo_path: Path,
        config: DriftConfig,
    ) -> tuple[BaselineSnapshot, list[Finding], dict[str, ParseResult]] | None:
        """Load a persisted nudge baseline if key and schema match."""
        repo_key = repo_path.resolve().as_posix()
        key_meta = self._compute_nudge_key_meta(repo_path, config)
        path = self._nudge_baseline_path(repo_path, config.cache_dir, key_meta)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            if payload.get("schema_version") != _NUDGE_BASELINE_SCHEMA_VERSION:
                return None
            if payload.get("head_commit") != key_meta[0]:
                return None
            if payload.get("config_fingerprint") != key_meta[1]:
                return None

            raw_hashes = payload.get("file_hashes")
            if not isinstance(raw_hashes, dict):
                return None
            file_hashes = {
                str(k): str(v)
                for k, v in raw_hashes.items()
                if isinstance(k, str) and isinstance(v, str)
            }

            raw_findings = payload.get("findings")
            findings: list[Finding] = []
            if isinstance(raw_findings, list):
                for entry in raw_findings:
                    if isinstance(entry, dict):
                        finding = self._deserialize_finding(entry)
                        if finding is not None:
                            findings.append(finding)

            baseline = BaselineSnapshot(
                file_hashes=file_hashes,
                score=float(payload.get("score", 0.0)),
                created_at=float(payload.get("created_at", time.time())),
                ttl_seconds=int(payload.get("ttl_seconds", 900)),
            )
            self._nudge_key_meta[repo_key] = key_meta
            git_state = _capture_git_state(repo_path)
            if git_state is not None:
                self._git_state[repo_key] = git_state
            return (baseline, findings, {})
        except Exception:
            logger.debug(
                "Failed to load persisted nudge baseline from %s",
                path,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            return None

    @staticmethod
    def _serialize_finding(finding: Finding) -> dict[str, Any]:
        """Convert Finding into a JSON-safe dictionary for baseline storage."""
        return {
            "signal_type": finding.signal_type,
            "severity": finding.severity.value,
            "score": finding.score,
            "title": finding.title,
            "description": finding.description,
            "file_path": finding.file_path.as_posix() if finding.file_path else None,
            "start_line": finding.start_line,
            "end_line": finding.end_line,
            "symbol": finding.symbol,
            "related_files": [p.as_posix() for p in finding.related_files],
            "ai_attributed": finding.ai_attributed,
            "fix": finding.fix,
            "impact": finding.impact,
            "score_contribution": finding.score_contribution,
            "metadata": finding.metadata,
            "rule_id": finding.rule_id,
            "language": finding.language,
            "finding_context": finding.finding_context,
        }

    @staticmethod
    def _deserialize_finding(entry: dict[str, Any]) -> Finding | None:
        """Recreate Finding from persistent baseline payload."""
        from drift.models import Severity

        try:
            severity = Severity(str(entry.get("severity", "medium")))
            file_path_raw = entry.get("file_path")
            related_files_raw = entry.get("related_files", [])
            related_files = [Path(p) for p in related_files_raw if isinstance(p, str)]
            metadata = entry.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            return Finding(
                signal_type=str(entry.get("signal_type", "unknown")),
                severity=severity,
                score=float(entry.get("score", 0.0)),
                title=str(entry.get("title", "")),
                description=str(entry.get("description", "")),
                file_path=Path(file_path_raw) if isinstance(file_path_raw, str) else None,
                start_line=int(entry["start_line"])
                if entry.get("start_line") is not None
                else None,
                end_line=int(entry["end_line"]) if entry.get("end_line") is not None else None,
                symbol=str(entry["symbol"]) if entry.get("symbol") is not None else None,
                related_files=related_files,
                ai_attributed=bool(entry.get("ai_attributed", False)),
                fix=str(entry["fix"]) if entry.get("fix") is not None else None,
                impact=float(entry.get("impact", 0.0)),
                score_contribution=float(entry.get("score_contribution", 0.0)),
                metadata=metadata,
                rule_id=str(entry["rule_id"]) if entry.get("rule_id") is not None else None,
                language=str(entry["language"]) if entry.get("language") is not None else None,
                finding_context=(
                    str(entry["finding_context"])
                    if entry.get("finding_context") is not None
                    else None
                ),
            )
        except Exception:
            return None


# ---------------------------------------------------------------------------
# IncrementalSignalRunner
# ---------------------------------------------------------------------------


class IncrementalSignalRunner:
    """Run file-local signals on changed files; carry forward others.

    This runner is deliberately conservative: cross-file and git-dependent
    signals are **not** re-executed — their baseline findings are reused
    with ``confidence: "estimated"``.  Only file-local signals produce
    exact results.

    Parameters
    ----------
    baseline:
        Snapshot captured after the last full scan.
    config:
        Drift configuration (weights, thresholds, etc.).
    baseline_findings:
        Findings produced by the full scan that created *baseline*.
    baseline_parse_results:
        ParseResults from the baseline scan, keyed by posix path.
    """

    def __init__(
        self,
        *,
        baseline: BaselineSnapshot,
        config: DriftConfig,
        baseline_findings: list[Finding],
        baseline_parse_results: dict[str, ParseResult],
    ) -> None:
        self._baseline = baseline
        self._config = config
        self._baseline_findings = baseline_findings
        self._baseline_parse_map = baseline_parse_results

    # ------------------------------------------------------------------

    def run(
        self,
        changed_files: set[str],
        current_parse_results: dict[str, ParseResult],
    ) -> IncrementalResult:
        """Execute incremental analysis for *changed_files*.

        Parameters
        ----------
        changed_files:
            Set of posix file paths that were added, removed, or modified.
        current_parse_results:
            Fresh ``ParseResult`` objects for the changed files (and
            optionally unchanged files — they will be merged).
        """
        from drift.scoring.engine import composite_score, compute_signal_scores
        from drift.signals.base import (
            BaseSignal,
            SignalCapabilities,
            _instantiate_signal,
            registered_signals,
        )

        # 1. Build merged parse_results: baseline + overwritten changed files
        merged: dict[str, ParseResult] = dict(self._baseline_parse_map)
        for path in changed_files:
            if path in current_parse_results:
                merged[path] = current_parse_results[path]
            else:
                # File was removed
                merged.pop(path, None)

        # 2. Classify registered signals
        file_local_classes: list[type[BaseSignal]] = []
        other_classes: list[type[BaseSignal]] = []
        for cls in registered_signals():
            if cls.incremental_scope == "file_local":
                file_local_classes.append(cls)
            else:
                other_classes.append(cls)

        # 3. Run file-local signals on changed-file parse results only
        changed_prs = [pr for path, pr in merged.items() if path in changed_files]
        removed_files = {path for path in changed_files if path not in current_parse_results}
        file_local_findings: list[Finding] = []
        file_local_signal_names: list[str] = []

        from pathlib import Path as _Path

        dummy_caps = SignalCapabilities(
            repo_path=_Path("."),
            embedding_service=None,
            commits=[],
        )

        for cls in file_local_classes:
            try:
                inst = _instantiate_signal(cls, dummy_caps)
                inst.bind_context(dummy_caps)
                findings = inst.analyze(changed_prs, {}, self._config)
                file_local_findings.extend(findings)
                st = getattr(inst, "signal_type", None)
                if st is not None:
                    file_local_signal_names.append(st.value)
            except Exception as exc:
                logger.warning(
                    "Incremental signal '%s' failed; skipping. %s: %s",
                    cls.__name__,
                    type(exc).__name__,
                    exc,
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )

        # 4. Carry forward non-file-local findings from baseline
        #    but drop findings for files that were changed (stale)
        # Use a simpler approach: if a finding's signal_type is NOT in file_local,
        # it's cross-file/git and should be carried forward.
        file_local_st_values = set(file_local_signal_names)

        carried_findings: list[Finding] = []
        pruned_removed_cross_file_findings = 0
        for f in self._baseline_findings:
            if f.signal_type in file_local_st_values:
                # File-local findings for unchanged files — keep them
                fp = f.file_path.as_posix() if f.file_path else ""
                if fp not in changed_files:
                    carried_findings.append(f)
            else:
                # Cross-file / git findings remain estimated, but findings for
                # removed files must not survive the incremental merge.
                fp = f.file_path.as_posix() if f.file_path else ""
                if fp in removed_files:
                    pruned_removed_cross_file_findings += 1
                    continue
                carried_findings.append(f)

        cross_file_signal_names: list[str] = sorted(
            {f.signal_type for f in carried_findings if f.signal_type not in file_local_st_values},
        )

        # 5. Merge and score
        all_findings = carried_findings + file_local_findings
        signal_scores = compute_signal_scores(all_findings)
        score = composite_score(signal_scores, self._config.weights)

        # 6. Diff findings vs baseline
        baseline_keys = {_finding_key(f) for f in self._baseline_findings}
        current_keys = {_finding_key(f) for f in all_findings}

        new_findings = [f for f in all_findings if _finding_key(f) not in baseline_keys]
        resolved_findings = [
            f for f in self._baseline_findings if _finding_key(f) not in current_keys
        ]

        # 7. Confidence map
        confidence: dict[str, Literal["exact", "estimated"]] = {}
        for name in file_local_signal_names:
            confidence[name] = "exact"
        for name in cross_file_signal_names:
            confidence[name] = "estimated"

        delta = score - self._baseline.score

        return IncrementalResult(
            score=score,
            delta=round(delta, 4),
            direction=_direction_for_delta(delta),
            new_findings=new_findings,
            resolved_findings=resolved_findings,
            confidence=confidence,
            file_local_signals_run=sorted(file_local_signal_names),
            cross_file_signals_estimated=cross_file_signal_names,
            baseline_valid=self._baseline.is_valid(),
            pruned_removed_cross_file_findings=pruned_removed_cross_file_findings,
        )
