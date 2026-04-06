"""Incremental analysis foundation for Drift.

Provides:

* ``BaselineSnapshot`` — lightweight checkpoint of analysis state.
* ``IncrementalResult`` — outcome of an incremental signal run.
* ``IncrementalSignalRunner`` — runs only the signals affected by file changes.
* ``BaselineManager`` — singleton that manages baselines with git-event detection.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

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
            p
            for p in baseline_keys & current_keys
            if self.file_hashes[p] != current_hashes[p]
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
    return f"{f.signal_type.value}::{fp}::{f.start_line}::{f.title}"


# ---------------------------------------------------------------------------
# Git state tracking (Phase 5 — Step 19)
# ---------------------------------------------------------------------------

_MAX_CHANGED_FILES_BEFORE_INVALIDATION = 10


@dataclass(slots=True)
class _GitState:
    """Captures point-in-time git state for change detection."""

    head_commit: str
    stash_hash: str  # hash of ``git stash list`` output
    changed_file_count: int


def _capture_git_state(repo_path: Path) -> _GitState | None:
    """Snapshot current HEAD, stash list, and dirty-file count.

    Returns ``None`` when git is unavailable or the path is not a repo.
    """
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
    ) -> tuple[BaselineSnapshot, list[Finding], dict[str, ParseResult]] | None:
        """Return stored baseline or ``None`` if missing / expired / invalidated.

        Performs a git-state check: if HEAD, stash, or changed-file count
        diverged since the baseline was stored, the entry is silently
        invalidated and ``None`` is returned.
        """
        repo_key = repo_path.resolve().as_posix()
        stored = self._store.get(repo_key)
        if stored is None:
            self._last_refresh_reason[repo_key] = "baseline_missing"
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
    ) -> None:
        """Cache a baseline and snapshot the current git state."""
        repo_key = repo_path.resolve().as_posix()
        self._store[repo_key] = (baseline, findings, parse_map)
        self._last_refresh_reason.pop(repo_key, None)

        git_state = _capture_git_state(repo_path)
        if git_state is not None:
            self._git_state[repo_key] = git_state

    def invalidate(self, repo_path: Path) -> None:
        """Remove cached baseline for *repo_path*."""
        repo_key = repo_path.resolve().as_posix()
        self._store.pop(repo_key, None)
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

        current = _capture_git_state(repo_path)
        if current is None:
            return None

        # (a) Branch switch or new commit
        if current.head_commit != previous.head_commit:
            return "git_head_changed"

        # (b) Stash changed
        if current.stash_hash != previous.stash_hash:
            return "stash_changed"

        # (c) Many files changed since baseline was stored
        if current.changed_file_count > _MAX_CHANGED_FILES_BEFORE_INVALIDATION:
            return "changed_file_threshold"

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
        changed_prs = [
            pr for path, pr in merged.items() if path in changed_files
        ]
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
        for f in self._baseline_findings:
            if f.signal_type.value in file_local_st_values:
                # File-local findings for unchanged files — keep them
                fp = f.file_path.as_posix() if f.file_path else ""
                if fp not in changed_files:
                    carried_findings.append(f)
            else:
                # Cross-file / git findings — carry all forward
                carried_findings.append(f)

        cross_file_signal_names: list[str] = sorted(
            {
                f.signal_type.value
                for f in carried_findings
                if f.signal_type.value not in file_local_st_values
            },
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
        )
