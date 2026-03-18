"""Signal 7: System Misalignment Score (SMS).

Detects when a change — typically an AI-generated PR — introduces
patterns, dependencies or conventions not established in the target
module, solving its local task correctly but weakening global cohesion.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from drift.models import (
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal


def _module_imports(parse_results: list[ParseResult]) -> dict[Path, set[str]]:
    """Map each module directory to the set of external modules it imports."""
    module_imports: dict[Path, set[str]] = defaultdict(set)
    for pr in parse_results:
        module = pr.file_path.parent
        for imp in pr.imports:
            if not imp.is_relative:
                # Use top-level package name
                top = imp.imported_module.split(".")[0]
                module_imports[module].add(top)
    return module_imports


def _find_novel_imports(
    parse_results: list[ParseResult],
    module_import_baseline: dict[Path, set[str]],
    file_histories: dict[str, FileHistory],
    recency_days: int = 14,
) -> list[tuple[ImportInfo, Path, str]]:
    """Find imports in recent files that introduce novel dependencies to their module."""
    novel: list[tuple[ImportInfo, Path, str]] = []

    import datetime

    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        days=recency_days
    )

    for pr in parse_results:
        fpath_str = pr.file_path.as_posix()
        history = file_histories.get(fpath_str)
        if not history or not history.last_modified:
            continue

        last_mod = history.last_modified
        if hasattr(last_mod, "astimezone"):
            last_mod = last_mod.astimezone(datetime.timezone.utc)
        if last_mod < cutoff:
            continue

        module = pr.file_path.parent
        baseline = module_import_baseline.get(module, set())

        for imp in pr.imports:
            if imp.is_relative:
                continue
            top = imp.imported_module.split(".")[0]
            if top not in baseline:
                novel.append((imp, module, top))

    return novel


class SystemMisalignmentSignal(BaseSignal):
    """Detect changes that introduce foreign patterns into existing modules."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SYSTEM_MISALIGNMENT

    @property
    def name(self) -> str:
        return "System Misalignment"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        # Build baseline of established imports per module
        baseline = _module_imports(parse_results)

        # Find novel imports in recently-modified files
        novel = _find_novel_imports(parse_results, baseline, file_histories)

        findings: list[Finding] = []
        # Group by module
        by_module: dict[Path, list[tuple[ImportInfo, str]]] = defaultdict(list)
        for imp, module, pkg in novel:
            by_module[module].append((imp, pkg))

        for module, imports in by_module.items():
            unique_packages = {pkg for _, pkg in imports}
            if not unique_packages:
                continue

            score = min(1.0, len(unique_packages) * 0.25)

            severity = Severity.INFO
            if score >= 0.6:
                severity = Severity.MEDIUM
            elif score >= 0.3:
                severity = Severity.LOW

            pkg_list = ", ".join(sorted(unique_packages))
            imp_details = [
                f"  - {imp.source_file}:{imp.line_number} imports '{pkg}'"
                for imp, pkg in imports[:5]
            ]

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=round(score, 3),
                    title=f"Novel dependencies in {module.as_posix()}/",
                    description=(
                        f"Recently introduced {len(unique_packages)} package(s) "
                        f"not previously used in this module: {pkg_list}\n"
                        + "\n".join(imp_details)
                    ),
                    file_path=module,
                    metadata={
                        "novel_packages": sorted(unique_packages),
                        "import_count": len(imports),
                    },
                )
            )

        return findings

    def score(self, findings: list[Finding]) -> float:
        if not findings:
            return 0.0
        return sum(f.score for f in findings) / len(findings)
