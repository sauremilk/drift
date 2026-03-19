"""Signal 2: Architecture Violation Score (AVS).

Detects imports that violate layer boundaries — e.g. a route handler
importing directly from a database module instead of going through
a service layer.

Enhancements over v0.1:
- Omnilayer recognition: config/utils/types modules are cross-cutting
  and never generate violations.
- Hub-module dampening: high-centrality targets get reduced scores.
- Embedding-based layer inference (optional): uses semantic similarity
  to layer-prototype descriptions when sentence-transformers is installed.
- Policy ``allowed_cross_layer`` patterns suppress matching findings.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

if TYPE_CHECKING:
    from drift.embeddings import EmbeddingService

logger = logging.getLogger("drift.avs")


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


# ---------------------------------------------------------------------------
# Layer inference
# ---------------------------------------------------------------------------

# Sentinel for cross-cutting modules that may be imported from any layer.
_OMNILAYER = -1

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

_OMNILAYER_DIRS: set[str] = {
    "config",
    "settings",
    "constants",
    "types",
    "utils",
    "helpers",
    "common",
    "shared",
    "base",
    "exceptions",
    "errors",
    "enums",
    "schemas",
}

# Layer-prototype descriptions for embedding-based inference.
_LAYER_PROTOTYPES: dict[int, str] = {
    0: "HTTP request handling, route, endpoint, REST API, web handler, response",
    1: "business logic, service, domain, use case, orchestration, workflow",
    2: "database, query, model, repository, ORM, storage, persistence, SQL",
    _OMNILAYER: "configuration, settings, constants, utilities, helpers, types, enums",
}


def _infer_layer(path: Path) -> int | None:
    """Infer the architectural layer from directory name.

    Returns ``_OMNILAYER`` for cross-cutting modules, a layer int for
    recognised layer directories, or ``None`` when no layer can be
    inferred.
    """
    for part in path.parts:
        low = part.lower()
        if low in _OMNILAYER_DIRS:
            return _OMNILAYER
        if low in _DEFAULT_LAYERS:
            return _DEFAULT_LAYERS[low]
    return None


def _infer_layer_with_embeddings(
    path: Path,
    parse_result: ParseResult | None,
    emb: EmbeddingService,
    proto_embeddings: dict[int, Any],
) -> int | None:
    """Embedding-enhanced layer inference.

    Falls back to directory-name inference when no strong semantic match
    is found.
    """
    # Try directory-name first
    layer = _infer_layer(path)
    if layer is not None:
        return layer

    # Build a text representation from the file's docstrings/imports
    if parse_result is None:
        return None

    parts: list[str] = []
    for fn in parse_result.functions[:5]:
        parts.append(fn.name)
    for imp in parse_result.imports[:10]:
        parts.append(imp.imported_module)

    if not parts:
        return None

    text = " ".join(parts)
    vec = emb.embed_text(text)
    if vec is None:
        return None

    best_layer = None
    best_sim = 0.0
    for layer_id, proto_vec in proto_embeddings.items():
        sim = emb.cosine_similarity(vec, proto_vec)
        if sim > best_sim:
            best_sim = sim
            best_layer = layer_id

    if best_sim >= 0.5 and best_layer is not None:
        return best_layer
    return None


# ---------------------------------------------------------------------------
# Hub-module detection via centrality
# ---------------------------------------------------------------------------


def _compute_hub_nodes(graph: nx.DiGraph, percentile: float = 0.90) -> set[str]:
    """Find hub nodes with in-degree centrality above *percentile*."""
    if graph.number_of_nodes() < 3:
        return set()
    centrality = nx.in_degree_centrality(graph)
    if not centrality:
        return set()
    values = sorted(centrality.values())
    cutoff_idx = int(len(values) * percentile)
    cutoff_val = values[min(cutoff_idx, len(values) - 1)]
    return {node for node, c in centrality.items() if c >= cutoff_val and c > 0}


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


@register_signal
class ArchitectureViolationSignal(BaseSignal):
    """Detect imports that violate architectural layer boundaries."""

    _embedding_service: EmbeddingService | None = None  # set by create_signals

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
        config: DriftConfig,
    ) -> list[Finding]:
        graph, all_imports = build_import_graph(parse_results)
        findings: list[Finding] = []

        # Pre-compute per-file lookup for embedding inference
        pr_by_path: dict[str, ParseResult] = {pr.file_path.as_posix(): pr for pr in parse_results}

        # Pre-compute embedding prototypes once
        proto_embeddings: dict[int, Any] = {}
        emb = getattr(self, "_embedding_service", None)
        if emb is not None:
            for layer_id, text in _LAYER_PROTOTYPES.items():
                vec = emb.embed_text(text)
                if vec is not None:
                    proto_embeddings[layer_id] = vec

        # Compute hub nodes for score dampening
        hub_nodes = _compute_hub_nodes(graph)

        # Collect allowed_cross_layer patterns
        policies = getattr(config, "policies", None) if config else None
        allowed_patterns: list[str] = getattr(policies, "allowed_cross_layer", []) or []

        # --- Check configured layer boundaries ---
        if policies and hasattr(policies, "layer_boundaries"):
            for boundary in policies.layer_boundaries:
                findings.extend(self._check_boundary(boundary, all_imports, parse_results))

        # --- Check inferred layer violations (upward imports) ---
        findings.extend(
            self._check_inferred_layers(
                graph,
                parse_results,
                pr_by_path,
                emb,
                proto_embeddings,
                hub_nodes,
                allowed_patterns,
            )
        )

        # --- Check for circular dependencies ---
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
                if _matches_pattern(target, deny) or _matches_pattern(imp.imported_module, deny):
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
        pr_by_path: dict[str, ParseResult],
        emb: EmbeddingService | None,
        proto_embeddings: dict[int, Any],
        hub_nodes: set[str],
        allowed_patterns: list[str],
    ) -> list[Finding]:
        findings: list[Finding] = []

        for src, dst, data in graph.edges(data=True):
            if graph.nodes.get(dst, {}).get("external"):
                continue

            # Infer layers (with optional embedding enhancement)
            if emb is not None and proto_embeddings:
                src_layer = _infer_layer_with_embeddings(
                    Path(src), pr_by_path.get(src), emb, proto_embeddings
                )
                dst_layer = _infer_layer_with_embeddings(
                    Path(dst), pr_by_path.get(dst), emb, proto_embeddings
                )
            else:
                src_layer = _infer_layer(Path(src))
                dst_layer = _infer_layer(Path(dst))

            if src_layer is None or dst_layer is None:
                continue

            # Omnilayer modules never cause violations
            if src_layer == _OMNILAYER or dst_layer == _OMNILAYER:
                continue

            # Check allowed_cross_layer patterns
            if any(
                _matches_pattern(src, pat) or _matches_pattern(dst, pat) for pat in allowed_patterns
            ):
                continue

            # Upward import: higher-numbered layer (infra) importing lower (API)
            if src_layer > dst_layer:
                imp_info = data.get("import_info")
                line = imp_info.line_number if imp_info else 0

                score = 0.5
                # Dampen score for hub-module targets (0.5× instead
                # of 0.3× — less aggressive to reduce false negatives
                # on legitimate architectural violations via hubs).
                if dst in hub_nodes:
                    score *= 0.5

                # Filter out very low-confidence findings
                if score < 0.15:
                    continue

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.MEDIUM,
                        score=score,
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
                            "hub_dampened": dst in hub_nodes,
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

        for reported, scc in enumerate(sorted(sccs, key=len, reverse=True)):
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

        return findings
