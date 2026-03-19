"""Signal 6: Temporal Volatility Score (TVS).

Detects modules with anomalous change patterns — high churn,
many authors, defect-correlated commits — especially when
combined with AI attribution.
"""

from __future__ import annotations

import math
from typing import Any

from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal


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


class TemporalVolatilitySignal(BaseSignal):
    """Detect files with anomalous churn and defect correlation."""

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
        config: Any,
    ) -> list[Finding]:
        if not file_histories:
            return []

        histories = list(file_histories.values())

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

        findings: list[Finding] = []

        # Resolve z-threshold from config
        z_threshold = 1.5
        if hasattr(config, "thresholds"):
            z_threshold = config.thresholds.volatility_z_threshold

        for history in histories:
            freq_z = _z_score(history.change_frequency_30d, freq_mean, freq_std)
            author_z = _z_score(float(history.unique_authors), author_mean, author_std)
            defect_z = _z_score(
                float(history.defect_correlated_commits), defect_mean, defect_std
            )

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
                    f"{history.unique_authors} unique authors "
                    f"({author_z:.1f}σ above mean)"
                )
            if defect_z > z_threshold:
                desc_parts.append(
                    f"{history.defect_correlated_commits} defect-correlated commits "
                    f"({defect_z:.1f}σ above mean)"
                )
            if ai_ratio > 0.0:
                desc_parts.append(f"AI-attributed: {ai_ratio:.0%}")

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=round(score, 3),
                    title=f"High volatility: {history.path.as_posix()}",
                    description=". ".join(desc_parts) + ".",
                    file_path=history.path,
                    ai_attributed=ai_ratio > 0.3,
                    metadata={
                        "change_frequency_30d": round(history.change_frequency_30d, 2),
                        "unique_authors": history.unique_authors,
                        "defect_correlated": history.defect_correlated_commits,
                        "ai_ratio": round(ai_ratio, 3),
                        "freq_z": round(freq_z, 2),
                        "author_z": round(author_z, 2),
                        "defect_z": round(defect_z, 2),
                    },
                )
            )

        return findings
