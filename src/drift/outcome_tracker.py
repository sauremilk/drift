"""Outcome tracking for drift findings across analysis runs.

Records when findings are first detected and when they disappear,
enabling measurement of fix speed and downstream recommendation quality.
All data is stored locally in JSONL format — no network, no LLM.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from drift.calibration._atomic_io import atomic_write_text, interprocess_lock
from drift.models import Finding, FindingStatus

logger = logging.getLogger(__name__)


@dataclass
class Outcome:
    """Tracked lifecycle of a single finding across analysis runs."""

    fingerprint: str
    signal_type: str
    recommendation_title: str
    reported_at: str  # ISO-8601
    resolved_at: str | None = None  # ISO-8601 or None
    days_to_fix: float | None = None
    effort_estimate: str = "medium"  # "low" | "medium" | "high"
    was_suppressed: bool = False


def compute_fingerprint(finding: Finding) -> str:
    """Compute a stable SHA-256 fingerprint for a finding.

    Uses ``LogicalLocation.fully_qualified_name`` when available (stable
    across line-number shifts), otherwise falls back to file path + start
    line.  The signal type is always part of the hash so that different
    signals on the same location produce distinct fingerprints.
    """
    if finding.logical_location and finding.logical_location.fully_qualified_name:
        key = f"{finding.signal_type}:{finding.logical_location.fully_qualified_name}"
    elif finding.file_path is not None:
        key = f"{finding.signal_type}:{finding.file_path.as_posix()}:{finding.start_line or 0}"
    else:
        key = f"{finding.signal_type}:{finding.title}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class OutcomeTracker:
    """Persists finding outcomes in a repo-local JSONL file.

    Parameters
    ----------
    outcomes_path:
        Path to the JSONL file (typically ``.drift/outcomes.jsonl``).
    """

    def __init__(self, outcomes_path: Path) -> None:
        self._path = outcomes_path
        self._session_fingerprints: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, finding: Finding, effort_estimate: str = "medium") -> None:
        """Record a finding observed in the current analysis run.

        Idempotent within a single session — repeated calls for the same
        fingerprint are silently ignored (F-06).
        """
        fp = compute_fingerprint(finding)
        if fp in self._session_fingerprints:
            return
        self._session_fingerprints.add(fp)

        with interprocess_lock(self._path):
            # Check whether this fingerprint already has an *active* entry.
            existing = self._load_unlocked()
            for outcome in existing:
                if outcome.fingerprint == fp and outcome.resolved_at is None:
                    return  # still tracked, nothing to do

            outcome = Outcome(
                fingerprint=fp,
                signal_type=finding.signal_type,
                recommendation_title=finding.title,
                reported_at=datetime.now(UTC).isoformat(),
                was_suppressed=finding.status == FindingStatus.SUPPRESSED,
                effort_estimate=effort_estimate,
            )
            self._append_unlocked(outcome)

    def resolve(
        self,
        current_fingerprints: set[str],
        active_signal_types: set[str] | None = None,
    ) -> list[Outcome]:
        """Mark findings that are no longer present as resolved.

        Parameters
        ----------
        current_fingerprints:
            Fingerprints observed in the current analysis run.
        active_signal_types:
            Optional set of currently active signal types. If provided,
            unresolved outcomes for signal types outside this set are
            resolved as stale.

        Returns the list of newly resolved outcomes.
        """
        with interprocess_lock(self._path):
            outcomes = self._load_unlocked()
            now = datetime.now(UTC)
            resolved: list[Outcome] = []

            for outcome in outcomes:
                if outcome.resolved_at is not None:
                    continue

                signal_inactive = (
                    active_signal_types is not None
                    and outcome.signal_type not in active_signal_types
                )
                if outcome.fingerprint in current_fingerprints and not signal_inactive:
                    continue

                outcome.resolved_at = now.isoformat()
                reported = datetime.fromisoformat(outcome.reported_at)
                outcome.days_to_fix = (now - reported).total_seconds() / 86400.0
                resolved.append(outcome)

            if resolved:
                self._rewrite_unlocked(outcomes)

            return resolved

    def load(self) -> list[Outcome]:
        """Load all outcomes from the JSONL file.

        Returns an empty list when the file does not exist (F-05).
        """
        with interprocess_lock(self._path):
            return self._load_unlocked()

    def archive(self, max_age_days: int = 180) -> int:
        """Move outcomes older than *max_age_days* to an archive file.

        Returns the number of archived entries.
        """
        with interprocess_lock(self._path):
            # Finalize any previously interrupted archive operation first.
            pending = self._load_pending_archive()
            if pending:
                self._merge_into_archive(pending)
                self._clear_pending_archive()

            outcomes = self._load_unlocked()
            now = datetime.now(UTC)
            keep: list[Outcome] = []
            archived: list[Outcome] = []

            for outcome in outcomes:
                reported = datetime.fromisoformat(outcome.reported_at)
                age_days = (now - reported).total_seconds() / 86400.0
                if age_days > max_age_days and outcome.resolved_at is not None:
                    archived.append(outcome)
                else:
                    keep.append(outcome)

            if not archived:
                return 0

            # Store pending archive payload first, then atomically rewrite active file,
            # then merge into archive. If a crash happens in-between, next archive()
            # run can finalize from the pending file without duplicate archive entries.
            self._write_pending_archive(archived)
            self._rewrite_unlocked(keep)
            self._merge_into_archive(archived)
            self._clear_pending_archive()
            return len(archived)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, outcome: Outcome) -> None:
        with interprocess_lock(self._path):
            self._append_unlocked(outcome)

    def _append_unlocked(self, outcome: Outcome) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(outcome), ensure_ascii=False) + "\n")

    def _rewrite(self, outcomes: list[Outcome]) -> None:
        with interprocess_lock(self._path):
            self._rewrite_unlocked(outcomes)

    def _rewrite_unlocked(self, outcomes: list[Outcome]) -> None:
        self._write_outcomes_atomically(self._path, outcomes)

    def _load_unlocked(self) -> list[Outcome]:
        if not self._path.exists():
            return []

        outcomes: list[Outcome] = []
        skipped = 0
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            outcome = self._deserialize_outcome(data)
            if outcome is None:
                skipped += 1
                continue
            outcomes.append(outcome)

        if skipped:
            logger.warning(
                "OutcomeTracker: skipped %d unreadable entries in %s",
                skipped,
                self._path,
            )
        return outcomes

    def _archive_path(self) -> Path:
        return self._path.with_suffix(".archive.jsonl")

    def _archive_pending_path(self) -> Path:
        return self._path.with_suffix(".archive.pending.json")

    def _outcome_key(self, outcome: Outcome) -> tuple[str, str, str | None, str]:
        return (
            outcome.fingerprint,
            outcome.reported_at,
            outcome.resolved_at,
            outcome.signal_type,
        )

    def _deserialize_outcome(self, data: object) -> Outcome | None:
        if not isinstance(data, dict):
            return None

        # Ignore unknown keys so older/newer schema variants remain readable.
        known_fields = Outcome.__dataclass_fields__
        filtered = {key: value for key, value in data.items() if key in known_fields}
        try:
            return Outcome(**filtered)
        except TypeError:
            return None

    def _write_outcomes_atomically(self, path: Path, outcomes: list[Outcome]) -> None:
        content = "".join(
            json.dumps(asdict(outcome), ensure_ascii=False) + "\n" for outcome in outcomes
        )
        atomic_write_text(path, content, encoding="utf-8")

    def _load_outcomes_from_path(self, path: Path) -> list[Outcome]:
        if not path.exists():
            return []
        loaded: list[Outcome] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                loaded.append(Outcome(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
        return loaded

    def _write_pending_archive(self, outcomes: list[Outcome]) -> None:
        pending_data = [asdict(outcome) for outcome in outcomes]
        atomic_write_text(
            self._archive_pending_path(),
            json.dumps(pending_data, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _load_pending_archive(self) -> list[Outcome]:
        pending_path = self._archive_pending_path()
        if not pending_path.exists():
            return []
        try:
            raw = json.loads(pending_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            pending: list[Outcome] = []
            for item in raw:
                if isinstance(item, dict):
                    try:
                        pending.append(Outcome(**item))
                    except TypeError:
                        continue
            return pending
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _clear_pending_archive(self) -> None:
        self._archive_pending_path().unlink(missing_ok=True)

    def _merge_into_archive(self, outcomes: list[Outcome]) -> None:
        archive_path = self._archive_path()
        existing = self._load_outcomes_from_path(archive_path)
        seen = {self._outcome_key(outcome) for outcome in existing}
        merged = list(existing)
        for outcome in outcomes:
            key = self._outcome_key(outcome)
            if key in seen:
                continue
            seen.add(key)
            merged.append(outcome)
        self._write_outcomes_atomically(archive_path, merged)
