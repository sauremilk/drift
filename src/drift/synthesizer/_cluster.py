"""Cluster engine — groups recurring findings across scan snapshots."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Literal

from drift.calibration.feedback import FeedbackEvent
from drift.calibration.history import ScanSnapshot
from drift.synthesizer._models import (
    ClusterFeedback,
    FindingCluster,
    _compute_cluster_id,
)

# Trend detection noise floor — deltas smaller than this are STABLE.
_NOISE_FLOOR = 0.005


def _stable_dir(file_path: str) -> str:
    """Derive a stable directory key from a file path (line-independent)."""
    return str(PurePosixPath(file_path).parent)


def _resolve_module_path(
    file_dir: str,
    known_modules: list[str] | None = None,
) -> str:
    """Map a file directory to the longest matching known module path.

    Falls back to the directory itself if no known modules provided.
    Re-uses the longest-prefix strategy from ``_skill_generator``.
    """
    if not known_modules:
        return file_dir
    best = file_dir
    best_len = 0
    for mod in known_modules:
        normalised = mod.replace("\\", "/")
        if file_dir.startswith(normalised) and len(normalised) > best_len:
            best = normalised
            best_len = len(normalised)
    return best


def _compute_trend(
    scores: list[float],
) -> Literal["improving", "stable", "degrading"]:
    """Derive trend from a sequence of per-scan occurrence counts/scores."""
    if len(scores) < 2:
        return "stable"
    first_half = scores[: len(scores) // 2]
    second_half = scores[len(scores) // 2 :]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    delta = avg_second - avg_first
    if delta > _NOISE_FLOOR:
        return "degrading"
    if delta < -_NOISE_FLOOR:
        return "improving"
    return "stable"


def build_finding_clusters(
    snapshots: list[ScanSnapshot],
    feedback_events: list[FeedbackEvent] | None = None,
    *,
    known_modules: list[str] | None = None,
    min_recurrence: int = 3,
    min_recurrence_rate: float = 0.5,
) -> list[FindingCluster]:
    """Cluster recurring findings across scan snapshots.

    Parameters
    ----------
    snapshots:
        Chronologically ordered scan snapshots (oldest first).
    feedback_events:
        Optional calibration feedback for TP/FP/FN enrichment.
    known_modules:
        Module paths from ArchGraph for longest-prefix resolution.
    min_recurrence:
        Minimum total occurrences across scans to qualify.
    min_recurrence_rate:
        Minimum fraction of scans a cluster must appear in.

    Returns
    -------
    list[FindingCluster]
        Filtered, enriched clusters sorted by occurrence_count descending.
    """
    if not snapshots:
        return []

    # --- Step 1: Aggregate findings by stable key -------------------------
    # Key: (signal_type, module_path, rule_id)

    agg: dict[tuple[str, str, str | None], dict] = defaultdict(
        lambda: {
            "files": set(),
            "scan_indices": set(),
            "per_scan_counts": [],
            "representatives": [],
            "timestamps": [],
        },
    )

    for scan_idx, snapshot in enumerate(snapshots):
        # Count per stable key within this scan
        scan_counts: dict[tuple[str, str, str | None], int] = defaultdict(int)
        for finding in snapshot.findings:
            file_dir = _stable_dir(finding.file_path)
            module = _resolve_module_path(file_dir, known_modules)
            # FindingSnapshot doesn't carry rule_id; use None
            rule_id: str | None = None
            key = (finding.signal_type, module, rule_id)
            scan_counts[key] += 1
            agg[key]["files"].add(finding.file_path)
            agg[key]["scan_indices"].add(scan_idx)
            agg[key]["timestamps"].append(snapshot.timestamp)
            # Keep up to 5 representative findings
            if len(agg[key]["representatives"]) < 5:
                agg[key]["representatives"].append(finding)

        for key, count in scan_counts.items():
            agg[key]["per_scan_counts"].append(count)

    total_scans = len(snapshots)

    # --- Step 2: Build clusters and apply filters -------------------------
    clusters: list[FindingCluster] = []
    for (signal_type, module_path, rule_id), data in agg.items():
        occurrence_count = sum(data["per_scan_counts"])
        scans_present = len(data["scan_indices"])
        recurrence_rate = scans_present / total_scans if total_scans > 0 else 0.0

        if occurrence_count < min_recurrence:
            continue
        if recurrence_rate < min_recurrence_rate:
            continue

        timestamps = sorted(data["timestamps"])
        trend = _compute_trend([float(c) for c in data["per_scan_counts"]])

        cluster_id = _compute_cluster_id(signal_type, module_path, rule_id)
        clusters.append(
            FindingCluster(
                cluster_id=cluster_id,
                signal_type=signal_type,
                rule_id=rule_id,
                module_path=module_path,
                affected_files=sorted(data["files"]),
                occurrence_count=occurrence_count,
                recurrence_rate=round(recurrence_rate, 3),
                first_seen=timestamps[0] if timestamps else "",
                last_seen=timestamps[-1] if timestamps else "",
                trend=trend,
                feedback=ClusterFeedback(),
                representative_findings=list(data["representatives"][:5]),
            ),
        )

    # --- Step 3: Enrich with feedback data --------------------------------
    if feedback_events:
        _enrich_feedback(clusters, feedback_events)

    # Sort by occurrence_count descending
    clusters.sort(key=lambda c: c.occurrence_count, reverse=True)
    return clusters


def _enrich_feedback(
    clusters: list[FindingCluster],
    events: list[FeedbackEvent],
) -> None:
    """Match feedback events to clusters and aggregate TP/FP/FN."""
    for cluster in clusters:
        fb = ClusterFeedback()
        for event in events:
            if event.signal_type != cluster.signal_type:
                continue
            # Match by file_path prefix (module-level)
            event_dir = _stable_dir(event.file_path)
            if not event_dir.startswith(cluster.module_path):
                continue
            if event.verdict == "tp":
                fb.tp += 1
            elif event.verdict == "fp":
                fb.fp += 1
            elif event.verdict == "fn":
                fb.fn += 1
        cluster.feedback = fb
