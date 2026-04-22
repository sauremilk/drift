"""JSONL-Reader/Writer fuer den Outcome-Feedback-Ledger (ADR-088)."""

from __future__ import annotations

from pathlib import Path

from drift.outcome_ledger._models import MergeTrajectory


def append_trajectory(ledger_path: Path, trajectory: MergeTrajectory) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = trajectory.model_dump_json()
    with ledger_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.write("\n")


def load_trajectories(ledger_path: Path) -> list[MergeTrajectory]:
    if not ledger_path.exists():
        return []
    out: list[MergeTrajectory] = []
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        out.append(MergeTrajectory.model_validate_json(line))
    return out


__all__ = ["append_trajectory", "load_trajectories"]
