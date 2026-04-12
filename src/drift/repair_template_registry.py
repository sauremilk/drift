"""Repair Template Registry — learns from successful fixes (ADR-065).

Collects outcome evidence from ``drift_nudge`` calls (``improving`` / ``regressing``)
and exposes per-(signal, edit_kind, context_class) confidence scores and known
regression patterns to coding agents via :class:`AgentTask` fields.

Design principles:
- **No LLM**: all data is derived mechanically from nudge outcome logs.
- **Closed enum for regression reasons**: :class:`~drift.models.RegressionReasonCode`
  \u2014 no free text that could drift or hallucinate.
- **Confidence = None when data is thin**: fewer than
  :data:`MIN_OUTCOMES_FOR_CONFIDENCE` recorded outcomes \u2192 ``None`` (do not
  over-trust early data).
- **outcomes.jsonl is git-ignored**: user-local file with repo-relative paths
  \u2014 never committed silently.
- **Seed file is committed**: ``data/repair_templates/templates.json`` provides
  an immediate baseline derived from the benchmark suite.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from drift.models import RegressionPattern, RegressionReasonCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

#: Minimum outcome count before ``confidence()`` returns a non-None value.
#: Prevents over-trusting early / sparse data.
MIN_OUTCOMES_FOR_CONFIDENCE: int = 3

#: Default seed path inside the drift package data directory.
#: Relative to the package root; resolved at load time.
_DEFAULT_SEED_PATH = (
    Path(__file__).parent.parent.parent / "data" / "repair_templates" / "templates.json"
)
_DEFAULT_OUTCOMES_PATH = (
    Path(__file__).parent.parent.parent / "data" / "repair_templates" / "outcomes.jsonl"
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RepairTemplateEntry:
    """Aggregate outcome evidence for one (signal, edit_kind, context_class) triple.

    ``improving_count`` and ``regressing_count`` come from recorded nudge outcomes.
    ``regression_patterns`` lists known failure modes for this combination.
    """

    signal: str
    edit_kind: str
    context_class: str  # e.g. "production", "test", "production:local"
    improving_count: int = 0
    stable_count: int = 0
    regressing_count: int = 0
    regression_patterns: list[RegressionPattern] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    last_updated: str = ""  # ISO-8601

    @property
    def key(self) -> str:
        return f"{self.signal}:{self.edit_kind}:{self.context_class}"


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _regression_pattern_to_dict(rp: RegressionPattern) -> dict[str, Any]:
    return {
        "edit_kind": rp.edit_kind,
        "context_feature": rp.context_feature,
        "reason_code": str(rp.reason_code),
    }


def _regression_pattern_from_dict(d: dict[str, Any]) -> RegressionPattern:
    return RegressionPattern(
        edit_kind=d["edit_kind"],
        context_feature=d["context_feature"],
        reason_code=RegressionReasonCode(d["reason_code"]),
    )


def _entry_to_dict(e: RepairTemplateEntry) -> dict[str, Any]:
    return {
        "signal": e.signal,
        "edit_kind": e.edit_kind,
        "context_class": e.context_class,
        "improving_count": e.improving_count,
        "stable_count": e.stable_count,
        "regressing_count": e.regressing_count,
        "regression_patterns": [_regression_pattern_to_dict(rp) for rp in e.regression_patterns],
        "evidence_sources": e.evidence_sources,
        "last_updated": e.last_updated,
    }


def _entry_from_dict(d: dict[str, Any]) -> RepairTemplateEntry:
    return RepairTemplateEntry(
        signal=d["signal"],
        edit_kind=d["edit_kind"],
        context_class=d.get("context_class", "production"),
        improving_count=int(d.get("improving_count", 0)),
        stable_count=int(d.get("stable_count", 0)),
        regressing_count=int(d.get("regressing_count", 0)),
        regression_patterns=[
            _regression_pattern_from_dict(rp) for rp in d.get("regression_patterns", [])
        ],
        evidence_sources=list(d.get("evidence_sources", [])),
        last_updated=d.get("last_updated", ""),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RepairTemplateRegistry:
    """Outcome-based repair template store.

    Provides:
    - ``lookup(signal, edit_kind, context_class)``: retrieve an entry
    - ``confidence(entry)``: 0.0–1.0 or ``None`` when data is too thin
    - ``record_outcome(...)``: append an outcome to the local ``outcomes.jsonl``
    - ``rebuild_seed(seed_path, outcomes_path)``: aggregate log into a curated seed
    """

    def __init__(self) -> None:
        self._entries: dict[str, RepairTemplateEntry] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(
        self,
        seed_path: Path | None = None,
        outcomes_path: Path | None = None,
    ) -> None:
        """Load seed data and merge local outcome log into the registry.

        Safe to call multiple times (replaces existing state).

        Parameters
        ----------
        seed_path:
            Path to the committed ``templates.json`` seed file.
            Defaults to ``data/repair_templates/templates.json``.
        outcomes_path:
            Path to the user-local ``outcomes.jsonl`` file.
            Defaults to ``data/repair_templates/outcomes.jsonl``.
        """
        seed = seed_path or _DEFAULT_SEED_PATH
        outcomes = outcomes_path or _DEFAULT_OUTCOMES_PATH

        with self._lock:
            self._entries = {}
            self._load_seed(seed)
            self._load_outcomes(outcomes)

    def _load_seed(self, seed_path: Path) -> None:
        if not seed_path.exists():
            return
        try:
            raw = seed_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            for item in data.get("entries", []):
                entry = _entry_from_dict(item)
                self._entries[entry.key] = entry
        except Exception:
            logger.warning("repair_template_registry: failed to load seed %s", seed_path)

    def _load_outcomes(self, outcomes_path: Path) -> None:
        """Merge outcomes.jsonl into existing entries (additive)."""
        if not outcomes_path.exists():
            return
        try:
            for line in outcomes_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    self._apply_outcome_record(rec)
                except json.JSONDecodeError:
                    continue
        except Exception:
            logger.warning("repair_template_registry: failed to read outcomes %s", outcomes_path)

    def _apply_outcome_record(self, rec: dict[str, Any]) -> None:
        """Apply a single outcome record to the in-memory entries."""
        signal = rec.get("signal", "")
        edit_kind = rec.get("edit_kind", "")
        context_class = rec.get("context_class", "production")
        direction = rec.get("direction", "")

        if not signal or not edit_kind or direction not in ("improving", "stable", "regressing"):
            return

        key = f"{signal}:{edit_kind}:{context_class}"
        entry = self._entries.get(key)
        if entry is None:
            entry = RepairTemplateEntry(
                signal=signal,
                edit_kind=edit_kind,
                context_class=context_class,
            )
            self._entries[key] = entry

        if direction == "improving":
            entry.improving_count += 1
        elif direction == "stable":
            entry.stable_count += 1
        elif direction == "regressing":
            entry.regressing_count += 1

        entry.last_updated = rec.get("timestamp", datetime.datetime.now(datetime.UTC).isoformat())

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(
        self,
        signal: str,
        edit_kind: str,
        context_class: str = "production",
    ) -> RepairTemplateEntry | None:
        """Return the entry for (signal, edit_kind, context_class), or None.

        Falls back to wildcard context ``"*"`` when the exact context class
        has no entry.
        """
        with self._lock:
            exact_key = f"{signal}:{edit_kind}:{context_class}"
            entry = self._entries.get(exact_key)
            if entry is not None:
                return entry
            # Fallback: try without context
            wildcard_key = f"{signal}:{edit_kind}:*"
            return self._entries.get(wildcard_key)

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def confidence(self, entry: RepairTemplateEntry) -> float | None:
        """Return repair confidence for an entry, or None if data is too thin.

        Confidence = improving / (improving + regressing)
        Returns ``None`` when total (improving + regressing) < MIN_OUTCOMES_FOR_CONFIDENCE
        to prevent over-trusting early data.
        """
        total = entry.improving_count + entry.regressing_count
        if total < MIN_OUTCOMES_FOR_CONFIDENCE:
            return None
        return round(entry.improving_count / total, 3)

    # ------------------------------------------------------------------
    # Record outcome
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        *,
        signal: str,
        edit_kind: str,
        context_class: str = "production",
        direction: str,
        score_delta: float = 0.0,
        session_id: str = "",
        outcomes_path: Path | None = None,
    ) -> None:
        """Append one outcome record to outcomes.jsonl and update in-memory state.

        Only ``improving`` and ``regressing`` directions are recorded.
        ``stable`` and ``unknown`` are silently ignored (too ambiguous for
        template confidence computation).

        Failures are swallowed silently so that a write error never blocks
        the agent fix-loop.
        """
        if direction not in ("improving", "regressing"):
            return

        outcomes = outcomes_path or _DEFAULT_OUTCOMES_PATH

        record: dict[str, Any] = {
            "signal": signal,
            "edit_kind": edit_kind,
            "context_class": context_class,
            "direction": direction,
            "score_delta": round(score_delta, 6),
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }

        with self._lock:
            # Update in-memory state immediately
            self._apply_outcome_record(record)

            # Persist to outcomes.jsonl
            try:
                outcomes.parent.mkdir(parents=True, exist_ok=True)
                with outcomes.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception:
                logger.debug(
                    "repair_template_registry: could not write outcome to %s",
                    outcomes,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Rebuild seed
    # ------------------------------------------------------------------

    def rebuild_seed(
        self,
        seed_path: Path | None = None,
        outcomes_path: Path | None = None,
    ) -> None:
        """Aggregate the local outcomes.jsonl into the seed file.

        Merges all current in-memory entries (loaded from seed + outcomes)
        back into the seed file.  Intended for curated updates after
        accumulating sufficient local evidence.

        This method must be called explicitly; it is never called automatically.
        """
        seed = seed_path or _DEFAULT_SEED_PATH
        outcomes = outcomes_path or _DEFAULT_OUTCOMES_PATH

        # Re-load to ensure we have latest state
        self.load(seed_path=seed, outcomes_path=outcomes)

        with self._lock:
            data = {
                "entries": [
                    _entry_to_dict(e) for e in sorted(self._entries.values(), key=lambda e: e.key)
                ]
            }
            try:
                seed.parent.mkdir(parents=True, exist_ok=True)
                seed.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                logger.warning(
                    "repair_template_registry: failed to write seed %s", seed, exc_info=True
                )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: RepairTemplateRegistry | None = None
_registry_lock = Lock()


def get_registry() -> RepairTemplateRegistry:
    """Return the module-level singleton registry, loading it on first access."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = RepairTemplateRegistry()
                _registry.load()
    return _registry


def reset_registry() -> None:
    """Reset the singleton — for testing only."""
    global _registry
    with _registry_lock:
        _registry = None
