"""Scan history persistence for retrospective outcome correlation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class FindingSnapshot:
    """Minimal representation of a finding for history storage."""

    signal_type: str
    file_path: str
    start_line: int | None = None
    score: float = 0.0


@dataclass
class ScanSnapshot:
    """A point-in-time snapshot of scan results."""

    timestamp: str = ""
    drift_score: float = 0.0
    finding_count: int = 0
    findings: list[FindingSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


def save_snapshot(
    history_dir: Path,
    snapshot: ScanSnapshot,
    *,
    max_snapshots: int = 20,
) -> Path:
    """Save a scan snapshot to the history directory.

    Older snapshots beyond *max_snapshots* are pruned automatically.
    Returns the path of the saved snapshot file.
    """
    history_dir.mkdir(parents=True, exist_ok=True)

    # Use timestamp-based filename for natural ordering
    ts = snapshot.timestamp.replace(":", "-").replace("+", "_")
    filename = f"scan_{ts}.json"
    path = history_dir / filename

    data: dict[str, Any] = {
        "timestamp": snapshot.timestamp,
        "drift_score": snapshot.drift_score,
        "finding_count": snapshot.finding_count,
        "findings": [asdict(f) for f in snapshot.findings],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Prune old snapshots
    existing = sorted(history_dir.glob("scan_*.json"))
    while len(existing) > max_snapshots:
        oldest = existing.pop(0)
        oldest.unlink(missing_ok=True)

    return path


def load_snapshots(history_dir: Path) -> list[ScanSnapshot]:
    """Load all scan snapshots from the history directory, oldest first."""
    if not history_dir.exists():
        return []

    snapshots: list[ScanSnapshot] = []
    for path in sorted(history_dir.glob("scan_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            findings = [
                FindingSnapshot(**f) for f in data.get("findings", [])
            ]
            snapshots.append(
                ScanSnapshot(
                    timestamp=data.get("timestamp", ""),
                    drift_score=data.get("drift_score", 0.0),
                    finding_count=data.get("finding_count", 0),
                    findings=findings,
                )
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return snapshots
