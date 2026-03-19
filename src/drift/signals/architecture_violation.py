"""Signal 2: Architecture Violation Score (AVS).

Detects imports that violate layer boundaries — e.g. a route handler
importing directly from a database module instead of going through
a service layer.
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from drift.models import (
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal


def _module_for_path(path: Path) -> str:
    """Convert file path to a dotted module path."""
    parts = list(path.with_suffix("").parts)
    return ".".join(parts)


def _matches_pattern(path_str: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path_str, pattern)


def build_import_graph(
    parse_results: list[ParseResult],
) -> tuple[nx.DiGraph, list[ImportInfo]]:
    """Build a directed dependency graph from import statements."""
    graph = nx.DiGraph()
    all_imports: list[ImportInfo] = []

    known_files = {pr.file_path.as_posix() for pr in parse_results}
    known_modules = {_module_for_path(pr.file_path) for pr in parse_results}

    for pr in parse_results:
        src = pr.file_path.as_posix()
        graph.add_node(src)

        for imp in pr.imports:
            all_imports.append(imp)

            # Try to resolve the import to a known file
            target_module = imp.imported_module
            if target_module in known_modules:
                # Find the file that matches this module
                for kf in known_files:
                    if _module_for_path(Path(kf)) == target_module:
                        graph.add_edge(src, kf, import_info=imp)
                        break
            else:
                # External or unresolved — still record it
                graph.add_node(target_module, external=True)
                graph.add_edge(src, target_module, import_info=imp)

    return graph, all_imports


# Default layer inference from common directory names
_DEFAULT_LAYERS: dict[str, int] = {
    "api": 0,
    "routes": 0,
    "views": 0,
    "handlers": 0,
    "controllers": 0,
    "services": 1,
    "core": 1,
    "domain": 1,
    "use_cases": 1,
    "db": 2,
    "models": 2,
    "repositories": 2,
    "storage": 2,
    "infrastructure": 2,
}


def _infer_layer(path: Path) -> int | None:
    """Infer the architectural layer from directory name."""
    for part in path.parts:
        if part.lower() in _DEFAULT_LAYERS:
            return _DEFAULT_LAYERS[part.lower()]
    return None


class ArchitectureViolationSignal(BaseSignal):
    """Detect imports that violate architectural layer boundaries."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.ARCHITECTURE_VIOLATION

    @property
    def name(self) -> str:
        return "Architecture Violations"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        graph, all_imports = build_import_graph(parse_results)
        findings: list[Finding] = []

        # Check configured layer boundaries
        boundaries = getattr(config, "policies", None)
        if boundaries and hasattr(boundaries, "layer_boundaries"):
            for boundary in boundaries.layer_boundaries:
                findings.extend(
                    self._check_boundary(boundary, all_imports, parse_results)
                )

        # Check inferred layer violations (upward imports)
        findings.extend(self._check_inferred_layers(graph, parse_results))

        # Check for circular dependencies
        findings.extend(self._check_circular_deps(graph))

        return findings

    def _check_boundary(
        self,
        boundary: Any,
        all_imports: list[ImportInfo],
        parse_results: list[ParseResult],
    ) -> list[Finding]:
        findings: list[Finding] = []
        from_pattern = boundary.from_pattern
        deny_patterns = boundary.deny_import

        for imp in all_imports:
            src = imp.source_file.as_posix()
            if not _matches_pattern(src, from_pattern):
                continue

            for deny in deny_patterns:
                target = imp.imported_module.replace(".", "/")
                if _matches_pattern(target, deny) or _matches_pattern(
                    imp.imported_module, deny
                ):
                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.HIGH,
                            score=0.8,
                            title=f"Policy violation: {boundary.name}",
                            description=(
                                f"{imp.source_file}:{imp.line_number} imports "
                                f"'{imp.imported_module}' which violates boundary "
                                f"rule '{boundary.name}' (deny: {deny})"
                            ),
                            file_path=imp.source_file,
                            start_line=imp.line_number,
                            metadata={
                                "rule": boundary.name,
                                "import": imp.imported_module,
                            },
                        )
                    )

        return findings

    def _check_inferred_layers(
        self,
        graph: nx.DiGraph,
        parse_results: list[ParseResult],
    ) -> list[Finding]:
        findings: list[Finding] = []

        for src, dst, data in graph.edges(data=True):
            if graph.nodes.get(dst, {}).get("external"):
                continue

            src_layer = _infer_layer(Path(src))
            dst_layer = _infer_layer(Path(dst))

            if src_layer is None or dst_layer is None:
                continue

            # Upward import: higher-numbered layer (infra) importing lower (API)
            # In our scheme: 0 = presentation, 2 = data. Lower imports higher = OK.
            # Higher imports lower = violation.
            if src_layer > dst_layer:
                imp_info = data.get("import_info")
                line = imp_info.line_number if imp_info else 0

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.MEDIUM,
                        score=0.5,
                        title=f"Upward layer import: {Path(src).name} → {Path(dst).name}",
                        description=(
                            f"{src}:{line} — data/infrastructure layer imports from "
                            f"presentation/API layer. Expected direction: "
                            f"presentation → service → data."
                        ),
                        file_path=Path(src),
                        start_line=line,
                        related_files=[Path(dst)],
                        metadata={
                            "src_layer": src_layer,
                            "dst_layer": dst_layer,
                        },
                    )
                )

        return findings

    def _check_circular_deps(self, graph: nx.DiGraph) -> list[Finding]:
        findings: list[Finding] = []

        # simple_cycles is exponential on dense graphs. Use a bounded approach:
        # find strongly connected components first (linear), then only enumerate
        # cycles within small SCCs.
        sccs = [s for s in nx.strongly_connected_components(graph) if len(s) > 1]
        if not sccs:
            return findings

        reported = 0
        for scc in sorted(sccs, key=len, reverse=True):
            if reported >= 5:
                break
            cycle = sorted(scc)  # deterministic ordering
            cycle_str = " → ".join(Path(p).name for p in cycle)
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.MEDIUM,
                    score=0.6,
                    title=f"Circular dependency ({len(cycle)} modules)",
                    description=f"Cycle: {cycle_str}",
                    file_path=Path(cycle[0]),
                    related_files=[Path(p) for p in cycle[1:]],
                    metadata={"cycle": cycle},
                )
            )
            reported += 1

        return findings
