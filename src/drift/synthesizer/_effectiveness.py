"""Effectiveness tracking — measures if synthesized skills reduce recurrence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from drift.calibration.history import ScanSnapshot
from drift.synthesizer._cluster import build_finding_clusters
from drift.synthesizer._models import SkillEffectivenessRecord

_EFFECTIVENESS_FILE = "skill_effectiveness.jsonl"


def _effectiveness_path(cache_dir: Path) -> Path:
    return cache_dir / _EFFECTIVENESS_FILE


def load_effectiveness_records(
    cache_dir: Path,
) -> list[SkillEffectivenessRecord]:
    """Load all effectiveness records from the cache directory."""
    path = _effectiveness_path(cache_dir)
    if not path.is_file():
        return []
    records: list[SkillEffectivenessRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        records.append(
            SkillEffectivenessRecord(
                skill_name=data["skill_name"],
                created_at=data["created_at"],
                cluster_id=data["cluster_id"],
                pre_recurrence_rate=data["pre_recurrence_rate"],
                post_recurrence_rate=data.get("post_recurrence_rate"),
                scans_since_creation=data.get("scans_since_creation", 0),
            ),
        )
    return records


def save_effectiveness_record(
    record: SkillEffectivenessRecord,
    cache_dir: Path,
) -> None:
    """Append an effectiveness record to the JSONL file."""
    path = _effectiveness_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def create_effectiveness_baseline(
    skill_name: str,
    cluster_id: str,
    pre_recurrence_rate: float,
    cache_dir: Path,
) -> SkillEffectivenessRecord:
    """Create a baseline record when a skill is first adopted."""
    record = SkillEffectivenessRecord(
        skill_name=skill_name,
        created_at=datetime.now(UTC).isoformat(),
        cluster_id=cluster_id,
        pre_recurrence_rate=pre_recurrence_rate,
        post_recurrence_rate=None,
        scans_since_creation=0,
    )
    save_effectiveness_record(record, cache_dir)
    return record


def update_effectiveness(
    records: list[SkillEffectivenessRecord],
    snapshots: list[ScanSnapshot],
    cache_dir: Path,
) -> list[SkillEffectivenessRecord]:
    """Re-evaluate effectiveness for all tracked skills.

    Rebuilds clusters from recent snapshots and compares post-recurrence
    rates against the pre-creation baseline.
    """
    if not snapshots or not records:
        return records

    # Build clusters from current snapshot data
    clusters = build_finding_clusters(snapshots, min_recurrence=1, min_recurrence_rate=0.0)
    cluster_map = {c.cluster_id: c for c in clusters}

    updated: list[SkillEffectivenessRecord] = []
    for record in records:
        cluster = cluster_map.get(record.cluster_id)
        new_record = SkillEffectivenessRecord(
            skill_name=record.skill_name,
            created_at=record.created_at,
            cluster_id=record.cluster_id,
            pre_recurrence_rate=record.pre_recurrence_rate,
            post_recurrence_rate=cluster.recurrence_rate if cluster else 0.0,
            scans_since_creation=record.scans_since_creation + 1,
        )
        updated.append(new_record)

    # Overwrite the file with updated records
    path = _effectiveness_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in updated:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    return updated
