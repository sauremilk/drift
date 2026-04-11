"""Feedback event model and JSONL persistence for calibration evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


@dataclass
class FeedbackEvent:
    """A single calibration evidence data point.

    Each event records whether a specific finding was a true positive,
    false positive, or false negative, along with the source of the
    evidence and optional context.
    """

    signal_type: str
    file_path: str
    verdict: Literal["tp", "fp", "fn"]
    source: Literal["user", "inline_suppress", "inline_confirm", "git_correlation", "github_api"]
    start_line: int | None = None
    timestamp: str = ""
    finding_id: str = ""
    rule_id: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if not self.finding_id:
            self.finding_id = _compute_finding_id(
                self.signal_type, self.file_path, self.start_line
            )


def _compute_finding_id(
    signal_type: str, file_path: str, start_line: int | None = None,
) -> str:
    """Compute a stable finding identifier from signal + file (+ optional line)."""
    raw = f"{signal_type}:{file_path}"
    if start_line is not None:
        raw += f":{start_line}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def finding_id_for(
    signal_type: str, file_path: str, start_line: int | None = None,
) -> str:
    """Compute a stable finding identifier (public API)."""
    return _compute_finding_id(signal_type, file_path, start_line)


def record_feedback(
    feedback_path: Path,
    event: FeedbackEvent,
) -> None:
    """Append a feedback event to the JSONL file.

    Creates the parent directory and file if they don't exist.
    """
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
    with feedback_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_feedback(feedback_path: Path) -> list[FeedbackEvent]:
    """Load all feedback events from a JSONL file.

    Returns an empty list if the file does not exist.
    Silently skips malformed lines.
    """
    if not feedback_path.exists():
        return []

    events: list[FeedbackEvent] = []
    for line in feedback_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            events.append(FeedbackEvent(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return events


def feedback_summary(events: list[FeedbackEvent]) -> dict[str, dict[str, int]]:
    """Aggregate feedback events into per-signal TP/FP/FN counts.

    Returns::

        {
            "pattern_fragmentation": {"tp": 5, "fp": 2, "fn": 1},
            "architecture_violation": {"tp": 3, "fp": 0, "fn": 0},
            ...
        }
    """
    summary: dict[str, dict[str, int]] = {}
    for event in events:
        if event.signal_type not in summary:
            summary[event.signal_type] = {"tp": 0, "fp": 0, "fn": 0}
        summary[event.signal_type][event.verdict] += 1
    return summary


def feedback_summary_by_rule(
    events: list[FeedbackEvent],
) -> dict[str, dict[str, dict[str, int]]]:
    """Aggregate feedback events into per-signal, per-rule_id TP/FP/FN counts.

    Returns::

        {
            "architecture_violation": {
                "avs_co_change": {"tp": 2, "fp": 3, "fn": 0},
                "avs_upward_import": {"tp": 5, "fp": 0, "fn": 1},
                "": {"tp": 1, "fp": 0, "fn": 0},
            },
            ...
        }
    """
    summary: dict[str, dict[str, dict[str, int]]] = {}
    for event in events:
        signal = event.signal_type
        rule = event.rule_id or ""
        if signal not in summary:
            summary[signal] = {}
        if rule not in summary[signal]:
            summary[signal][rule] = {"tp": 0, "fp": 0, "fn": 0}
        summary[signal][rule][event.verdict] += 1
    return summary


# ---------------------------------------------------------------------------
# Per-signal feedback metrics (AP3)
# ---------------------------------------------------------------------------


@dataclass
class SignalFeedbackMetrics:
    """Precision/Recall/F1 metrics derived from feedback for a single signal."""

    signal_type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def total_observations(self) -> int:
        """Total TP + FP observations (excludes FN)."""
        return self.tp + self.fp

    @property
    def precision(self) -> float:
        """TP / (TP + FP). Returns 1.0 when no positive observations exist."""
        denom = self.tp + self.fp
        if denom == 0:
            return 1.0
        return self.tp / denom

    @property
    def recall(self) -> float:
        """TP / (TP + FN). Returns 1.0 when no relevant instances are known."""
        denom = self.tp + self.fn
        if denom == 0:
            return 1.0
        return self.tp / denom

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall."""
        p = self.precision
        r = self.recall
        if (p + r) == 0:
            return 0.0
        return 2.0 * p * r / (p + r)


def feedback_metrics(events: list[FeedbackEvent]) -> dict[str, SignalFeedbackMetrics]:
    """Compute per-signal precision/recall/F1 from feedback events.

    Returns a mapping from signal type to :class:`SignalFeedbackMetrics`.
    """
    counts = feedback_summary(events)
    result: dict[str, SignalFeedbackMetrics] = {}
    for signal_type, c in counts.items():
        result[signal_type] = SignalFeedbackMetrics(
            signal_type=signal_type,
            tp=c["tp"],
            fp=c["fp"],
            fn=c["fn"],
        )
    return result
