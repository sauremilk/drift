"""Signal 1: Pattern Fragmentation Score (PFS).

Detects when the same category of code pattern (e.g. error handling)
has multiple incompatible variants within the same module, indicating
inconsistent approaches — often from different AI generation sessions.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal


def _variant_key(fingerprint: dict[str, Any]) -> str:
    """Create a hashable key from a pattern fingerprint for grouping."""
    return json.dumps(fingerprint, sort_keys=True, default=str)


def _group_by_module(
    patterns: list[PatternInstance],
) -> dict[Path, list[PatternInstance]]:
    """Group patterns by their parent directory (module)."""
    groups: dict[Path, list[PatternInstance]] = defaultdict(list)
    for p in patterns:
        module = p.file_path.parent
        groups[module].append(p)
    return groups


def _count_variants(
    patterns: list[PatternInstance],
) -> dict[str, list[PatternInstance]]:
    """Group patterns by their fingerprint variant."""
    variants: dict[str, list[PatternInstance]] = defaultdict(list)
    for p in patterns:
        key = _variant_key(p.fingerprint)
        variants[key].append(p)
    return variants


def _canonical_variant(variants: dict[str, list[PatternInstance]]) -> str:
    """Identify the canonical (most-used) variant."""
    return max(variants, key=lambda k: len(variants[k]))


class PatternFragmentationSignal(BaseSignal):
    """Detect multiple incompatible pattern variants within architectural modules."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.PATTERN_FRAGMENTATION

    @property
    def name(self) -> str:
        return "Pattern Fragmentation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        # Gather all patterns from all files
        all_patterns: dict[PatternCategory, list[PatternInstance]] = defaultdict(list)
        for pr in parse_results:
            for pattern in pr.patterns:
                all_patterns[pattern.category].append(pattern)

        findings: list[Finding] = []

        for category, patterns in all_patterns.items():
            # Analyze per-module fragmentation
            module_groups = _group_by_module(patterns)

            for module_path, module_patterns in module_groups.items():
                if len(module_patterns) < 2:
                    continue

                variants = _count_variants(module_patterns)
                num_variants = len(variants)

                if num_variants <= 1:
                    continue

                canonical = _canonical_variant(variants)
                canonical_count = len(variants[canonical])
                total = len(module_patterns)
                non_canonical = [
                    p for key, ps in variants.items() if key != canonical for p in ps
                ]

                frag_score = 1 - (1 / num_variants)

                # Build description
                desc_parts = [
                    f"{num_variants} {category.value} variants in {module_path.as_posix()}/ "
                    f"({canonical_count}/{total} use canonical pattern).",
                ]
                for p in non_canonical[:3]:
                    desc_parts.append(
                        f"  - {p.file_path.name}:{p.start_line} ({p.function_name})"
                    )

                severity = Severity.INFO
                if frag_score >= 0.7:
                    severity = Severity.HIGH
                elif frag_score >= 0.5:
                    severity = Severity.MEDIUM
                elif frag_score >= 0.3:
                    severity = Severity.LOW

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=frag_score,
                        title=f"{category.value}: {num_variants} variants in {module_path.as_posix()}/",
                        description="\n".join(desc_parts),
                        file_path=module_path,
                        related_files=[p.file_path for p in non_canonical],
                        metadata={
                            "category": category.value,
                            "num_variants": num_variants,
                            "canonical_count": canonical_count,
                            "total_instances": total,
                        },
                    )
                )

        return findings

    def score(self, findings: list[Finding]) -> float:
        if not findings:
            return 0.0
        return sum(f.score for f in findings) / len(findings)
