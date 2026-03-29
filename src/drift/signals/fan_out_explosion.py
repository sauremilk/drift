"""Signal: Fan-Out Explosion (FOE).

Detects files that import an excessive number of unique modules,
indicating emerging "god files" that act as central coupling hubs.

High fan-out makes a file fragile: any change in its many dependencies
can break it, and the file itself becomes hard to reason about in
isolation.

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import _SUPPORTED_LANGUAGES, is_test_file
from drift.signals.base import BaseSignal, register_signal

# Index / barrel files that re-export are expected to have high fan-out.
_INDEX_NAMES: frozenset[str] = frozenset(
    {"__init__.py", "index.ts", "index.tsx", "index.js", "index.jsx"},
)


@register_signal
class FanOutExplosionSignal(BaseSignal):
    """Detect files with an excessive number of unique imports."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.FAN_OUT_EXPLOSION

    @property
    def name(self) -> str:
        return "Fan-Out Explosion"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        threshold = config.thresholds.foe_max_imports
        findings: list[Finding] = []

        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue
            if pr.file_path.name in _INDEX_NAMES:
                continue

            # Count unique imported modules
            unique_modules: set[str] = set()
            for imp in pr.imports:
                # Normalise to top-level package for relative imports
                module = imp.imported_module.split(".")[0] if imp.imported_module else ""
                if module:
                    unique_modules.add(imp.imported_module)

            count = len(unique_modules)
            if count <= threshold:
                continue

            overshoot = count - threshold
            score = round(min(1.0, 0.3 + overshoot * 0.035), 3)
            severity = Severity.HIGH if score >= 0.7 else Severity.MEDIUM

            related = [
                Path(mod.replace(".", "/"))
                for mod in sorted(unique_modules)[:10]
            ]

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=f"Fan-out explosion in {pr.file_path.name}",
                    description=(
                        f"{pr.file_path} imports {count} unique modules "
                        f"(threshold: {threshold}). High fan-out indicates "
                        f"a coupling hub that is fragile to upstream changes."
                    ),
                    file_path=pr.file_path,
                    related_files=related,
                    fix=(
                        f"Reduce import fan-out of {pr.file_path.name} "
                        f"(currently {count}, threshold {threshold}): "
                        f"split responsibilities into focused modules, "
                        f"introduce a facade or mediator to consolidate deps."
                    ),
                    metadata={
                        "unique_import_count": count,
                        "threshold": threshold,
                        "top_imports": sorted(unique_modules)[:20],
                    },
                    rule_id="fan_out_explosion",
                )
            )

        return findings
