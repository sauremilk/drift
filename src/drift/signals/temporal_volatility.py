"""Signal 6: Temporal Volatility Score (TVS).

Detects modules with anomalous change patterns — high churn,
many authors, defect-correlated commits — especially when
combined with AI attribution.
"""

from __future__ import annotations

import datetime
import math
from collections import defaultdict

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

_RUNTIME_PLUGIN_ROOTS: frozenset[str] = frozenset({"extensions", "plugins"})


def _runtime_plugin_workspace_key(path: str) -> str | None:
    """Return workspace key for runtime plugin monorepos."""
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    if parts[0] not in _RUNTIME_PLUGIN_ROOTS:
        return None
    return f"{parts[0]}/{parts[1]}"


def _z_score(value: float, mean: float, std: float) -> float:
    """Compute z-score, clamped to [-5, 5]."""
    if std < 0.001:
        return 0.0
    return max(-5.0, min(5.0, (value - mean) / std))


def _shannon_entropy(counts: list[int]) -> float:
    """Shannon entropy for author diversity."""
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def _workspace_burst_profiles(
    histories: list[FileHistory],
    *,
    freq_mean: float,
    freq_std: float,
    cutoff: datetime.datetime,
) -> dict[str, dict[str, bool]]:
    """Classify plugin workspaces to dampen expected development bursts.

    A workspace is considered bursty when many files change above baseline in
    a coordinated window. Brand-new workspaces are considered bursty by default.
    """
    by_workspace: dict[str, list[FileHistory]] = defaultdict(list)
    for history in histories:
        workspace = _runtime_plugin_workspace_key(history.path.as_posix())
        if workspace is None:
            continue
        by_workspace[workspace].append(history)

    profiles: dict[str, dict[str, bool]] = {}
    active_threshold = freq_mean + max(0.25, freq_std * 0.4)

    for workspace, ws_histories in by_workspace.items():
        if not ws_histories:
            continue

        established_count = 0
        active_count = 0
        for history in ws_histories:
            first_seen = history.first_seen
            if hasattr(first_seen, "astimezone"):
                first_seen = first_seen.astimezone(datetime.UTC)

            # Workspace age is determined by introduction time, not by whether
            # individual files have quiet periods after creation.
            if first_seen and first_seen < cutoff:
                established_count += 1
            if history.change_frequency_30d >= active_threshold:
                active_count += 1

        size = len(ws_histories)
        active_ratio = active_count / size
        workspace_is_new = established_count == 0
        coordinated_burst = size >= 6 and active_ratio >= 0.60

        profiles[workspace] = {
            "workspace_is_new": workspace_is_new,
            "coordinated_burst": coordinated_burst,
        }

    return profiles


@register_signal
class TemporalVolatilitySignal(BaseSignal):
    """Detect files with anomalous churn and defect correlation."""

    incremental_scope = "git_dependent"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.TEMPORAL_VOLATILITY

    @property
    def name(self) -> str:
        return "Temporal Volatility"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        """Flag files with statistically anomalous recent churn.

        Computes z-scores for change frequency, unique authors, and
        defect-correlated commits over a 30-day rolling window.
        A file is flagged when any z-score exceeds volatility_z_threshold.
        Requires git history; returns empty on shallow clones.
        """

        histories = list(file_histories.values())

        if not histories or all(h.total_commits == 0 for h in histories):
            self.emit_warning(
                "[TVS] No git history available — signal skipped. "
                "Run from a git repository with commit history for meaningful results."
            )
            return []

        # Compute baseline statistics
        freq_values = [h.change_frequency_30d for h in histories]
        author_values = [float(h.unique_authors) for h in histories]
        defect_values = [float(h.defect_correlated_commits) for h in histories]

        def _mean(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        def _std(vals: list[float]) -> float:
            if len(vals) < 2:
                return 0.0
            m = _mean(vals)
            return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))

        freq_mean, freq_std = _mean(freq_values), _std(freq_values)
        author_mean, author_std = _mean(author_values), _std(author_values)
        defect_mean, defect_std = _mean(defect_values), _std(defect_values)

        recency_days = 14
        if hasattr(config, "thresholds"):
            recency_days = config.thresholds.recency_days
        cutoff = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=recency_days)
        workspace_profiles = _workspace_burst_profiles(
            histories,
            freq_mean=freq_mean,
            freq_std=freq_std,
            cutoff=cutoff,
        )

        findings: list[Finding] = []

        # Resolve z-threshold from config
        z_threshold = 1.5
        if hasattr(config, "thresholds"):
            z_threshold = config.thresholds.volatility_z_threshold

        for history in histories:
            freq_z = _z_score(history.change_frequency_30d, freq_mean, freq_std)
            author_z = _z_score(float(history.unique_authors), author_mean, author_std)
            defect_z = _z_score(float(history.defect_correlated_commits), defect_mean, defect_std)

            # Composite volatility: any dimension > z_threshold is notable
            max_z = max(freq_z, author_z, defect_z)
            if max_z < z_threshold:
                continue

            # Score: normalized composite of z-scores
            composite = (freq_z + author_z + defect_z) / 3.0
            score = min(1.0, max(0.0, composite / 3.0))  # Normalize to 0..1

            # Boost score if AI-attributed
            ai_ratio = history.ai_attributed_commits / max(1, history.total_commits)
            if ai_ratio > 0.3:
                score = min(1.0, score * 1.3)

            workspace = _runtime_plugin_workspace_key(history.path.as_posix())
            workspace_profile = workspace_profiles.get(workspace or "")
            dampened_for_workspace_burst = False
            if workspace_profile and (
                workspace_profile["workspace_is_new"] or workspace_profile["coordinated_burst"]
            ):
                # Coordinated plugin workspace development is often intentional,
                # so cap severity impact to avoid high-confidence false positives.
                score = min(score, 0.45)
                dampened_for_workspace_burst = True

            if score < 0.2:
                continue

            severity = Severity.INFO
            if score >= 0.7:
                severity = Severity.HIGH
            elif score >= 0.5:
                severity = Severity.MEDIUM
            elif score >= 0.3:
                severity = Severity.LOW

            desc_parts = []
            if freq_z > z_threshold:
                desc_parts.append(
                    f"Change frequency: {history.change_frequency_30d:.1f}/week "
                    f"({freq_z:.1f}σ above mean)"
                )
            if author_z > z_threshold:
                desc_parts.append(
                    f"{history.unique_authors} unique authors ({author_z:.1f}σ above mean)"
                )
            if defect_z > z_threshold:
                desc_parts.append(
                    f"{history.defect_correlated_commits} defect-correlated commits "
                    f"({defect_z:.1f}σ above mean)"
                )
            if ai_ratio > 0.0:
                desc_parts.append(f"AI-attributed: {ai_ratio:.0%}")
            if dampened_for_workspace_burst:
                desc_parts.append("Extension/plugin workspace is in coordinated active development")

            fix_parts = []
            if freq_z > z_threshold:
                fix_parts.append(
                    f"{history.total_commits} commits in 30 days — "
                    "split the file into smaller modules"
                )
            if author_z > z_threshold:
                fix_parts.append(f"{history.unique_authors} authors — clarify ownership")
            if defect_z > z_threshold:
                fix_parts.append(
                    f"{history.defect_correlated_commits} defect-correlated commits"
                    " — stabilize with tests and code review"
                )
            fix = ". ".join(fix_parts) + "." if fix_parts else None

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=round(score, 3),
                    title=f"High volatility: {history.path.as_posix()}",
                    description=". ".join(desc_parts) + ".",
                    file_path=history.path,
                    ai_attributed=ai_ratio > 0.3,
                    fix=fix,
                    metadata={
                        "change_frequency_30d": round(history.change_frequency_30d, 2),
                        "unique_authors": history.unique_authors,
                        "defect_correlated": history.defect_correlated_commits,
                        "ai_ratio": round(ai_ratio, 3),
                        "freq_z": round(freq_z, 2),
                        "author_z": round(author_z, 2),
                        "defect_z": round(defect_z, 2),
                        "workspace_burst_dampened": dampened_for_workspace_burst,
                    },
                )
            )

        return findings
