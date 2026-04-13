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
- Configurable lazy-import policy rules detect module-level heavy imports.
"""

from __future__ import annotations

import fnmatch
import logging
import posixpath
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import networkx as nx

from drift.config import DriftConfig
from drift.ingestion.git_history import build_co_change_pairs
from drift.ingestion.test_detection import is_generated_file
from drift.models import (
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import is_test_file
from drift.signals.base import BaseSignal, register_signal

if TYPE_CHECKING:
    from drift.signals.base import EmbeddingServiceProtocol

logger = logging.getLogger("drift.avs")

_SOURCE_ROOT_PREFIXES: frozenset[str] = frozenset({"src", "lib", "python"})
_GENERATED_HEADER_MAX_LINES = 6


def _module_for_path(path: Path) -> str:
    """Convert file path to a dotted module path."""
    parts = list(path.with_suffix("").parts)
    return ".".join(parts)


def _module_aliases_for_path(path: Path) -> list[str]:
    """Return dotted module aliases for a file path.

    Repositories often keep importable packages under source roots like
    ``src/``. This helper maps both forms so imports such as
    ``transformers.utils`` can resolve to ``src/transformers/utils.py``.
    """
    module = _module_for_path(path)
    aliases = [module]

    parts = path.with_suffix("").parts
    if len(parts) >= 2 and parts[0].lower() in _SOURCE_ROOT_PREFIXES:
        aliases.append(".".join(parts[1:]))

    return aliases


def _matches_pattern(path_str: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path_str, pattern)


def _matches_module_pattern(module: str, pattern: str) -> bool:
    """Match module names against exact/prefix or glob-style patterns."""
    if _matches_pattern(module, pattern):
        return True
    if any(ch in pattern for ch in "*?[]"):
        return False
    return module == pattern or module.startswith(f"{pattern}.")


def _relative_import_candidates(source_file: Path, imp: ImportInfo) -> list[str]:
    """Build candidate module paths for unresolved relative imports.

    The Python parser currently records ``is_relative`` but stores
    ``imported_module`` without leading dots. For large codebases that use
    package-relative imports heavily, this can collapse internal edges into
    unresolved externals. This helper reconstructs best-effort candidates from
    the source file package path.
    """
    if not imp.is_relative:
        return []

    source_parts = list(source_file.with_suffix("").parts)
    if len(source_parts) < 2:
        return []

    base_parts = source_parts[:-1]
    module = (imp.imported_module or "").strip(".").strip()

    candidates: list[str] = []
    if module:
        candidates.append(".".join(base_parts + module.split(".")))
    else:
        for name in imp.imported_names:
            token = (name or "").strip()
            if token and token != "*":
                candidates.append(".".join(base_parts + [token]))

    if module:
        module_parts = module.split(".")
        for name in imp.imported_names:
            token = (name or "").strip()
            if token and token != "*":
                candidates.append(".".join(base_parts + module_parts + [token]))

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _relative_path_candidates(source_file: Path, module_spec: str) -> list[str]:
    """Build path-like candidates for relative import specifiers.

    Handles TS/JS ESM conventions such as ``./foo.js`` pointing at
    ``./foo.ts`` as well as extension-less relative specifiers.
    """
    spec = (module_spec or "").strip()
    if not spec.startswith("."):
        return []

    source_dir = PurePosixPath(source_file.as_posix()).parent
    joined = source_dir.as_posix() + "/" + spec
    base = posixpath.normpath(joined)

    ext_aliases: dict[str, tuple[str, ...]] = {
        ".js": (".js", ".ts", ".tsx"),
        ".jsx": (".jsx", ".tsx"),
        ".mjs": (".mjs", ".mts"),
        ".cjs": (".cjs", ".cts"),
    }

    p = PurePosixPath(base)
    candidates: list[str] = [p.as_posix()]
    suffix = p.suffix.lower()
    if suffix in ext_aliases:
        stem = p.with_suffix("").as_posix()
        candidates.extend(stem + ext for ext in ext_aliases[suffix])
    elif suffix == "":
        stem = p.as_posix()
        candidates.extend(
            stem + ext
            for ext in (
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".mts",
                ".cts",
                ".mjs",
                ".cjs",
            )
        )

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _extension_workspace_root(path_str: str) -> str | None:
    """Return extensions/<name> workspace root for a repo path, if present."""
    parts = PurePosixPath(path_str).parts
    if len(parts) >= 2 and parts[0] == "extensions":
        return f"extensions/{parts[1]}"
    return None


def _has_generated_header(path: Path) -> bool:
    """Return True when the first lines contain explicit auto-generated markers."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            header = "".join(
                next(handle, "") for _ in range(_GENERATED_HEADER_MAX_LINES)
            ).lower()
    except OSError:
        return False

    return (
        "auto-generated" in header
        or "autogenerated" in header
        or ("generated by" in header and "do not edit" in header)
    )


def _is_passive_definition_module(parse_result: ParseResult | None) -> bool:
    """Return True for files that only carry passive definitions.

    These modules often contain constants/type shapes and intentionally
    no executable logic. They should not be treated as "Zone of Pain"
    architecture hotspots.
    """
    if parse_result is None:
        return False
    if parse_result.parse_errors:
        return False

    return (
        not parse_result.imports
        and not parse_result.functions
        and not parse_result.classes
        and not parse_result.patterns
        and parse_result.line_count > 0
    )


def build_import_graph(
    parse_results: list[ParseResult],
) -> tuple[nx.DiGraph, list[ImportInfo]]:
    """Build a directed dependency graph from import statements.

    Complexity: O(n + m) where n = files, m = total imports.
    Nodes are files (or unresolved external modules). Edges are import
    relationships. Downstream analysis uses in-degree centrality for hub
    detection and Tarjan's SCC algorithm for circular dependency detection.
    """
    graph = nx.DiGraph()
    all_imports: list[ImportInfo] = []

    # Build a direct module -> file lookup once to avoid repeated linear scans
    # over all known files for every import in large repositories.
    module_to_file: dict[str, str] = {}
    path_to_file: dict[str, str] = {}
    for pr in parse_results:
        file_posix = pr.file_path.as_posix()
        path_to_file.setdefault(file_posix, file_posix)
        path_to_file.setdefault(pr.file_path.with_suffix("").as_posix(), file_posix)
        parts = pr.file_path.parts
        if len(parts) >= 2 and parts[0].lower() in _SOURCE_ROOT_PREFIXES:
            trimmed = Path(*parts[1:])
            path_to_file.setdefault(trimmed.as_posix(), file_posix)
            path_to_file.setdefault(trimmed.with_suffix("").as_posix(), file_posix)
        for module_alias in _module_aliases_for_path(pr.file_path):
            module_to_file.setdefault(module_alias, file_posix)

    for pr in parse_results:
        src = pr.file_path.as_posix()
        graph.add_node(src)

        for imp in pr.imports:
            all_imports.append(imp)

            # Try to resolve the import to a known file
            target_module = imp.imported_module
            target_file = module_to_file.get(target_module)
            if target_file is None:
                target_file = path_to_file.get(target_module)
            if target_file is None and imp.is_relative:
                for candidate in _relative_import_candidates(pr.file_path, imp):
                    resolved = module_to_file.get(candidate)
                    if resolved is not None:
                        target_module = candidate
                        target_file = resolved
                        break
            if target_file is None and imp.is_relative:
                for candidate in _relative_path_candidates(pr.file_path, target_module):
                    resolved = path_to_file.get(candidate)
                    if resolved is not None:
                        target_module = candidate
                        target_file = resolved
                        break
            if target_file is not None:
                graph.add_edge(src, target_file, import_info=imp)
            else:
                # External or unresolved — still record it
                unresolved_target = target_module.strip()
                if not unresolved_target:
                    unresolved_target = ".".join(
                        n for n in imp.imported_names if n and n != "*"
                    ) or "<relative>"
                graph.add_node(unresolved_target, external=True)
                graph.add_edge(src, unresolved_target, import_info=imp)

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
    "scripts": 0,
    "commands": 0,
    "cli": 0,
    "services": 1,
    "core": 1,
    "domain": 1,
    "use_cases": 1,
    "db": 2,
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
    "models",
}

# Layer-prototype descriptions for embedding-based inference.
_LAYER_PROTOTYPES: dict[int, str] = {
    0: "HTTP request handling, route, endpoint, REST API, web handler, response",
    1: "business logic, service, domain, use case, orchestration, workflow",
    2: "database, query, model, repository, ORM, storage, persistence, SQL",
    _OMNILAYER: "configuration, settings, constants, utilities, helpers, types, enums",
}


def _infer_layer(path: Path, extra_omnilayer: set[str] | None = None) -> int | None:
    """Infer the architectural layer from directory name.

    Returns ``_OMNILAYER`` for cross-cutting modules, a layer int for
    recognised layer directories, or ``None`` when no layer can be
    inferred.
    """
    effective_omnilayer = _OMNILAYER_DIRS | extra_omnilayer if extra_omnilayer else _OMNILAYER_DIRS
    for part in path.parts:
        low = part.lower()
        if low in effective_omnilayer:
            return _OMNILAYER
        if low in _DEFAULT_LAYERS:
            return _DEFAULT_LAYERS[low]
    return None


def _infer_layer_with_embeddings(
    path: Path,
    parse_result: ParseResult | None,
    emb: EmbeddingServiceProtocol,
    proto_embeddings: dict[int, Any],
    extra_omnilayer: set[str] | None = None,
) -> int | None:
    """Embedding-enhanced layer inference.

    Falls back to directory-name inference when no strong semantic match
    is found.
    """
    # Try directory-name first
    layer = _infer_layer(path, extra_omnilayer=extra_omnilayer)
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

    uses_embeddings = True

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
        filtered_prs = [
            pr
            for pr in parse_results
            if not is_test_file(pr.file_path)
            and not is_generated_file(pr.file_path)
            and not _has_generated_header(pr.file_path)
        ]
        graph, all_imports = build_import_graph(filtered_prs)
        findings: list[Finding] = []

        # Pre-compute per-file lookup for embedding inference
        pr_by_path: dict[str, ParseResult] = {pr.file_path.as_posix(): pr for pr in filtered_prs}

        # Pre-compute embedding prototypes once
        proto_embeddings: dict[int, Any] = {}
        emb = self.embedding_service
        if emb is not None:
            for layer_id, text in _LAYER_PROTOTYPES.items():
                vec = emb.embed_text(text)
                if vec is not None:
                    proto_embeddings[layer_id] = vec

        # Compute hub nodes for score dampening
        hub_nodes = _compute_hub_nodes(graph)

        # Pre-compute transitive blast radius for internal nodes.
        # In the import graph edges go from importer → imported, so
        # *ancestors* of a node are all modules that transitively depend
        # on it — i.e. the set of modules affected by a change.
        blast_radius: dict[str, int] = {}
        internal_nodes = [n for n in graph.nodes if not graph.nodes.get(n, {}).get("external")]
        internal_set = set(internal_nodes)
        for node in internal_nodes:
            blast_radius[node] = len(nx.ancestors(graph, node) & internal_set)

        # Collect allowed_cross_layer patterns
        policies = getattr(config, "policies", None) if config else None
        allowed_patterns: list[str] = getattr(policies, "allowed_cross_layer", []) or []
        lazy_import_rules = getattr(policies, "lazy_import_rules", []) or []

        # --- Check configured layer boundaries ---
        if policies and hasattr(policies, "layer_boundaries"):
            for boundary in policies.layer_boundaries:
                findings.extend(self._check_boundary(boundary, all_imports, parse_results))

        # --- Check configured lazy-import policy rules ---
        if lazy_import_rules:
            findings.extend(self._check_lazy_import_rules(lazy_import_rules, all_imports))

        # --- Check inferred layer violations (upward imports) ---
        extra_omnilayer: set[str] | None = None
        if policies and policies.omnilayer_dirs:
            extra_omnilayer = set(policies.omnilayer_dirs)
        findings.extend(
            self._check_inferred_layers(
                graph,
                parse_results,
                pr_by_path,
                emb,
                proto_embeddings,
                hub_nodes,
                allowed_patterns,
                blast_radius,
                extra_omnilayer=extra_omnilayer,
            )
        )

        # --- Check for circular dependencies ---
        findings.extend(self._check_circular_deps(graph))

        # --- Check for high transitive blast radius ---
        findings.extend(self._check_blast_radius(blast_radius, internal_nodes, file_histories))

        # --- Check instability / distance from main sequence ---
        findings.extend(
            self._check_instability(graph, parse_results, pr_by_path, internal_nodes)
        )

        # --- Check for over-centralized modules (god modules) ---
        findings.extend(self._check_god_modules(graph, internal_nodes, blast_radius))

        # --- Check for unstable dependency smell ---
        findings.extend(
            self._check_unstable_dependencies(
                graph,
                internal_nodes,
                file_histories,
            )
        )

        # --- Check co-change coupling (hidden logical dependencies) ---
        commits = self.commits
        if commits:
            known = {pr.file_path.as_posix() for pr in filtered_prs}
            findings.extend(self._check_co_change(graph, commits, known))

        # --- Deduplicate findings by canonical semantic key ---
        seen: set[tuple[str, ...]] = set()
        deduped: list[Finding] = []
        for f in findings:
            key = self._finding_dedupe_key(f)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        return deduped

    def _finding_dedupe_key(self, finding: Finding) -> tuple[str, ...]:
        """Build a stable dedup key that collapses same-edge cross-pass AVS findings."""
        file_path = finding.file_path.as_posix() if finding.file_path else ""
        start_line = str(int(finding.start_line or 0))
        end_line = str(int(finding.end_line or 0))
        rule_id = finding.rule_id or str(self.signal_type)
        title = (finding.title or "").strip()

        # Policy-boundary and inferred-upward checks can report the same
        # source-line -> target edge with different titles. Collapse by edge.
        import_target = finding.metadata.get("import_target") if finding.metadata else None
        if isinstance(import_target, str) and import_target and int(start_line) > 0:
            return ("import-edge", file_path, start_line, import_target)

        if int(start_line) > 0 and finding.related_files:
            related = ",".join(sorted(p.as_posix() for p in finding.related_files))
            return ("line-related", rule_id, file_path, start_line, related)

        return ("generic", rule_id, file_path, start_line, end_line, title)

    def _check_boundary(
        self,
        boundary: Any,
        all_imports: list[ImportInfo],
        parse_results: list[ParseResult],
    ) -> list[Finding]:
        findings: list[Finding] = []
        from_pattern = boundary.from_pattern
        deny_patterns = boundary.deny_import

        module_to_file: dict[str, Path] = {}
        for pr in parse_results:
            module_to_file.setdefault(_module_for_path(pr.file_path), pr.file_path)

        for imp in all_imports:
            src = imp.source_file.as_posix()
            if not _matches_pattern(src, from_pattern):
                continue

            for deny in deny_patterns:
                target = imp.imported_module.replace(".", "/")
                if _matches_pattern(target, deny) or _matches_pattern(imp.imported_module, deny):
                    resolved_target = module_to_file.get(imp.imported_module)
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
                            related_files=[resolved_target] if resolved_target is not None else [],
                            fix=(
                                f"Remove import '{imp.imported_module}' in "
                                f"{imp.source_file.name}:{imp.line_number}. "
                                f"Route access through a service layer or interface."
                            ),
                            rule_id="avs_policy_boundary",
                            metadata={
                                "rule": boundary.name,
                                "import": imp.imported_module,
                                "import_target": (
                                    resolved_target.as_posix()
                                    if resolved_target is not None
                                    else imp.imported_module
                                ),
                            },
                        )
                    )

        return findings

    def _check_inferred_layers(
        self,
        graph: nx.DiGraph,
        parse_results: list[ParseResult],
        pr_by_path: dict[str, ParseResult],
        emb: EmbeddingServiceProtocol | None,
        proto_embeddings: dict[int, Any],
        hub_nodes: set[str],
        allowed_patterns: list[str],
        blast_radius: dict[str, int] | None = None,
        extra_omnilayer: set[str] | None = None,
    ) -> list[Finding]:
        """Flag cross-layer imports when no explicit policy boundaries exist.

        Infers architectural layers from directory structure and optional
        embedding-based prototype matching, then checks whether edges cross
        layer boundaries.  Hub modules (high in-degree) are dampened to
        reduce false positives from legitimate shared infrastructure.
        """
        findings: list[Finding] = []

        for src, dst, data in graph.edges(data=True):
            if graph.nodes.get(dst, {}).get("external"):
                continue

            # Infer layers (with optional embedding enhancement)
            if emb is not None and proto_embeddings:
                src_layer = _infer_layer_with_embeddings(
                    Path(src), pr_by_path.get(src), emb, proto_embeddings,
                    extra_omnilayer=extra_omnilayer,
                )
                dst_layer = _infer_layer_with_embeddings(
                    Path(dst), pr_by_path.get(dst), emb, proto_embeddings,
                    extra_omnilayer=extra_omnilayer,
                )
            else:
                src_layer = _infer_layer(Path(src), extra_omnilayer=extra_omnilayer)
                dst_layer = _infer_layer(Path(dst), extra_omnilayer=extra_omnilayer)

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
                        rule_id="avs_upward_import",
                        fix=(
                            f"Move {Path(dst).name} logic behind a service layer "
                            f"or abstraction interface that {Path(src).name} "
                            f"is allowed to import."
                        ),
                        metadata={
                            "src_layer": src_layer,
                            "dst_layer": dst_layer,
                            "hub_dampened": dst in hub_nodes,
                            "blast_radius": blast_radius.get(src, 0) if blast_radius else 0,
                            "import_target": dst,
                        },
                    )
                )

        return findings

    def _check_lazy_import_rules(
        self,
        rules: list[Any],
        all_imports: list[ImportInfo],
    ) -> list[Finding]:
        """Detect policy violations for heavy modules imported at module level."""
        findings: list[Finding] = []

        for rule in rules:
            from_pattern = getattr(rule, "from_pattern", "**/*.py")
            modules = getattr(rule, "modules", []) or []
            module_level_only = bool(getattr(rule, "module_level_only", True))
            if not modules:
                continue

            for imp in all_imports:
                src = imp.source_file.as_posix()
                if not _matches_pattern(src, from_pattern):
                    continue
                if module_level_only and not imp.is_module_level:
                    continue
                if not any(_matches_module_pattern(imp.imported_module, m) for m in modules):
                    continue

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.HIGH,
                        score=0.75,
                        title=f"Lazy-import policy violation: {rule.name}",
                        description=(
                            f"{imp.source_file}:{imp.line_number} imports "
                            f"'{imp.imported_module}' at module level, violating "
                            f"lazy-import policy rule '{rule.name}'."
                        ),
                        file_path=imp.source_file,
                        start_line=imp.line_number,
                        fix=(
                            f"Move import '{imp.imported_module}' in "
                            f"{imp.source_file.name}:{imp.line_number} into a local "
                            "function/class scope and initialize lazily at runtime."
                        ),
                        rule_id="avs_lazy_import_policy",
                        metadata={
                            "rule": rule.name,
                            "import": imp.imported_module,
                            "module_level_only": module_level_only,
                            "is_module_level": imp.is_module_level,
                            "lazy_import_target": imp.imported_module,
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
                    rule_id="avs_circular_dep",
                    description=f"Cycle: {cycle_str}",
                    file_path=Path(cycle[0]),
                    related_files=[Path(p) for p in cycle[1:]],
                    fix=(
                        f"Circular dependency ({len(cycle)} modules): {cycle_str}. "
                        f"Break the cycle via interface extraction or dependency inversion."
                    ),
                    metadata={"cycle": cycle},
                )
            )

        return findings

    def _check_blast_radius(
        self,
        blast_radius: dict[str, int],
        internal_nodes: list[str],
        file_histories: dict[str, FileHistory],
    ) -> list[Finding]:
        """Flag modules whose transitive blast radius is unusually high.

        A high blast radius means a change in that module transitively
        affects many downstream dependents, indicating poor encapsulation.
        """
        if not internal_nodes or not blast_radius:
            return []

        values = [blast_radius.get(n, 0) for n in internal_nodes]
        if not values:
            return []

        mean_br = sum(values) / len(values)
        # Only flag when there are enough modules to make the stat meaningful
        # and threshold is at least 5 transitive dependents.
        threshold = max(5, mean_br * 2)

        findings: list[Finding] = []
        for node in sorted(internal_nodes):
            br = blast_radius.get(node, 0)
            if br < threshold:
                continue
            # Churn guard: stable modules (change_frequency_30d <= 1.0) with
            # modest blast radius are not urgent — skip to avoid noise (ADR-050).
            fh = file_histories.get(node)
            churn = float(fh.change_frequency_30d) if fh is not None else 0.0
            if churn <= 1.0 and br <= 50:
                continue
            total = len(internal_nodes)
            pct = round(br / max(1, total - 1) * 100)
            score = min(1.0, round(br / max(1, total) * 0.8, 2))
            churn_note = f" Churn: {churn:.1f} changes/week." if churn > 0 else ""
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.MEDIUM if score < 0.6 else Severity.HIGH,
                    score=score,
                    title=(
                        f"High blast radius: {Path(node).name} "
                        f"({br} transitive dependents)"
                    ),
                    rule_id="avs_blast_radius",
                    description=(
                        f"A change in {node} transitively affects {br} of "
                        f"{total} modules ({pct}%). This indicates tight "
                        f"coupling and poor encapsulation.{churn_note}"
                    ),
                    file_path=Path(node),
                    fix=(
                        f"Refactor {Path(node).name} to reduce transitive coupling "
                        f"via interface extraction or by splitting into "
                        f"smaller, better-encapsulated modules."
                    ),
                    metadata={
                        "blast_radius": br,
                        "total_modules": total,
                        "blast_pct": pct,
                        "churn_per_week": round(churn, 2),
                    },
                )
            )
        return findings

    def _check_instability(
        self,
        graph: nx.DiGraph,
        parse_results: list[ParseResult],
        pr_by_path: dict[str, ParseResult],
        internal_nodes: list[str],
    ) -> list[Finding]:
        """Flag modules in the Zone of Pain (Robert C. Martin).

        Instability  I = Ce / (Ca + Ce)
        Abstraction  A = abstract_classes / total_classes  (0 if no classes)
        Distance     D = |A + I - 1|

        Modules with low abstraction AND low instability (D close to 1)
        are concrete and hard to change yet heavily depended upon —
        the "Zone of Pain".
        """
        if len(internal_nodes) < 4:
            return []

        findings: list[Finding] = []

        for node in internal_nodes:
            ca = graph.in_degree(node)   # afferent coupling
            ce = graph.out_degree(node)  # efferent coupling
            total_coupling = ca + ce
            if total_coupling == 0:
                continue

            instability = ce / total_coupling

            # Compute abstraction ratio from class info
            pr = pr_by_path.get(node)
            line_count = pr.line_count if pr is not None else 0
            total_classes = len(pr.classes) if pr is not None else 0
            function_count = len(pr.functions) if pr is not None else 0
            entity_count = total_classes + function_count

            # Passive constants/type-definition modules are expected to be
            # concrete and stable; Zone-of-Pain escalation is not useful there.
            if _is_passive_definition_module(pr):
                continue

            if pr is not None and total_classes > 0:
                abstract_count = 0
                for c in pr.classes:
                    if any(
                        b in ("ABC", "ABCMeta", "Protocol", "Interface")
                        for b in c.bases
                    ):
                        abstract_count += 1
                abstraction = abstract_count / total_classes
            else:
                abstraction = 0.0

            distance = abs(abstraction + instability - 1)

            # Zone of Pain: low instability (stable) + low abstraction
            # (concrete) → D ≈ 1.0 and I < 0.3
            if distance < 0.7 or instability > 0.5:
                continue
            # Only flag if enough dependents to matter
            if ca < 3:
                continue

            score = min(1.0, round(distance * 0.7, 2))
            # Tiny stable adapter/base modules can be legitimate foundations.
            # Keep the finding but require stronger coupling evidence for HIGH.
            tiny_foundational = (
                line_count > 0
                and line_count <= 20
                and entity_count <= 2
                and ce <= 1
            )
            has_high_risk_evidence = ca >= 6 or (ca >= 4 and ce >= 2)
            dampened_for_tiny_foundation = tiny_foundational and not has_high_risk_evidence
            if dampened_for_tiny_foundation:
                score = min(score, 0.49)

            severity = Severity.MEDIUM if score < 0.5 else Severity.HIGH
            evidence_note = (
                " Severity dampened for tiny foundational module; "
                "require stronger coupling evidence for HIGH."
                if dampened_for_tiny_foundation
                else ""
            )
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=(
                        f"Zone of Pain: {Path(node).name} "
                        f"(I={instability:.2f}, D={distance:.2f})"
                    ),
                    rule_id="avs_zone_of_pain",
                    description=(
                        f"{node} is concrete (A={abstraction:.2f}) and stable "
                        f"(I={instability:.2f}) with {ca} dependents. "
                        f"Distance from main sequence D={distance:.2f}. "
                        f"Changes here are costly and propagate widely."
                        f"{evidence_note}"
                    ),
                    file_path=Path(node),
                    fix=(
                        f"Extract abstractions (interfaces/protocols) from "
                        f"{Path(node).name} to invert dependencies, or reduce coupling."
                    ),
                    metadata={
                        "instability": round(instability, 3),
                        "abstraction": round(abstraction, 3),
                        "distance_main_seq": round(distance, 3),
                        "afferent_coupling": ca,
                        "efferent_coupling": ce,
                        "line_count": line_count,
                        "entity_count": entity_count,
                        "has_high_risk_evidence": has_high_risk_evidence,
                        "tiny_foundational_dampened": dampened_for_tiny_foundation,
                    },
                )
            )
        return findings

    def _check_god_modules(
        self,
        graph: nx.DiGraph,
        internal_nodes: list[str],
        blast_radius: dict[str, int],
    ) -> list[Finding]:
        """Detect modules with excessive centrality and dependency load.

        Heuristic:
        - unusually high total coupling (in + out)
        - non-trivial fan-in and fan-out
        - meaningful transitive blast radius
        """
        if len(internal_nodes) < 6:
            return []

        total_degrees: list[int] = [
            graph.in_degree(n) + graph.out_degree(n) for n in internal_nodes
        ]
        if not total_degrees:
            return []

        mean_degree = sum(total_degrees) / len(total_degrees)
        threshold = max(6, int(mean_degree * 2))

        findings: list[Finding] = []
        for node in sorted(internal_nodes):
            ca = graph.in_degree(node)
            ce = graph.out_degree(node)
            total = ca + ce
            br = blast_radius.get(node, 0)

            if total < threshold:
                continue
            if ca < 2 or ce < 2:
                continue
            if br < 3:
                continue

            score = min(1.0, round((total / max(1, len(internal_nodes))) * 1.5, 2))
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.MEDIUM if score < 0.6 else Severity.HIGH,
                    score=score,
                    title=f"God module candidate: {Path(node).name}",
                    rule_id="avs_god_module",
                    description=(
                        f"{node} has high coupling (Ca={ca}, Ce={ce}, total={total}) "
                        f"and blast radius {br}. This concentration of responsibilities "
                        f"increases change impact and architectural fragility."
                    ),
                    file_path=Path(node),
                    fix=(
                        f"Split {Path(node).name} by responsibility and extract stable "
                        f"interfaces to reduce fan-in and fan-out."
                    ),
                    metadata={
                        "afferent_coupling": ca,
                        "efferent_coupling": ce,
                        "total_coupling": total,
                        "blast_radius": br,
                        "god_module_threshold": threshold,
                    },
                )
            )
        return findings

    def _check_unstable_dependencies(
        self,
        graph: nx.DiGraph,
        internal_nodes: list[str],
        file_histories: dict[str, FileHistory],
    ) -> list[Finding]:
        """Detect stable modules depending on unstable/volatile modules.

        Approximates the Unstable Dependency smell by combining
        graph instability with observed recent change frequency.
        """
        if len(internal_nodes) < 4:
            return []

        instability: dict[str, float] = {}
        for node in internal_nodes:
            ca = graph.in_degree(node)
            ce = graph.out_degree(node)
            total = ca + ce
            instability[node] = ce / total if total > 0 else 0.0

        findings: list[Finding] = []
        for src, dst in graph.edges():
            if src not in instability or dst not in instability:
                continue
            if graph.nodes.get(dst, {}).get("external"):
                continue

            src_extension = _extension_workspace_root(src)
            dst_extension = _extension_workspace_root(dst)
            # In extension-based monorepos, intra-extension imports are expected
            # implementation detail wiring and should not be treated as AVS smell.
            if src_extension is not None and src_extension == dst_extension:
                continue

            src_ca = graph.in_degree(src)
            src_i = instability[src]
            dst_i = instability[dst]
            dst_hist = file_histories.get(dst)
            dst_churn = (
                float(dst_hist.change_frequency_30d)
                if dst_hist is not None
                else 0.0
            )

            # Stable source (widely depended upon + low instability)
            is_stable_src = src_ca >= 2 and src_i <= 0.40
            # Unstable dependency target (topology unstable and/or high churn)
            is_unstable_dst = dst_i >= 0.70 or dst_churn >= 1.0

            if not (is_stable_src and is_unstable_dst):
                continue

            score = min(1.0, round((dst_i * 0.6) + (min(dst_churn, 2.0) * 0.2), 2))
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.MEDIUM if score < 0.6 else Severity.HIGH,
                    score=score,
                    title=(
                        f"Unstable dependency: {Path(src).name} -> {Path(dst).name}"
                    ),
                    rule_id="avs_unstable_dep",
                    description=(
                        f"Stable module {src} (I={src_i:.2f}, Ca={src_ca}) depends on "
                        f"unstable/volatile module {dst} (I={dst_i:.2f}, "
                        f"churn/week={dst_churn:.2f})."
                    ),
                    file_path=Path(src),
                    related_files=[Path(dst)],
                    fix=(
                        f"Decouple {Path(src).name} from unstable module "
                        f"{Path(dst).name} using interface inversion or adapters "
                        f"so changes in {Path(dst).name} do not propagate upward."
                    ),
                    metadata={
                        "src_instability": round(src_i, 3),
                        "src_afferent": src_ca,
                        "dst_instability": round(dst_i, 3),
                        "dst_churn_week": round(dst_churn, 3),
                    },
                )
            )
        return findings

    def _check_co_change(
        self,
        graph: nx.DiGraph,
        commits: list,
        known_files: set[str],
    ) -> list[Finding]:
        """Flag file pairs with high co-change coupling but no import edge.

        These indicate hidden logical dependencies that the import graph
        does not capture — a strong signal for architectural drift.
        """
        pairs = build_co_change_pairs(commits, known_files)
        if not pairs:
            return []

        findings: list[Finding] = []
        for pair in pairs[:10]:  # cap to avoid noise
            # Only flag if there is NO static import relationship
            has_edge = (
                graph.has_edge(pair.file_a, pair.file_b)
                or graph.has_edge(pair.file_b, pair.file_a)
            )
            if has_edge:
                continue

            # Suppress same-directory co-evolution (sisters in a package).
            # Root-level files (parent == ".") are NOT suppressed to
            # preserve detection for flat-root repos.
            dir_a = str(PurePosixPath(pair.file_a).parent)
            dir_b = str(PurePosixPath(pair.file_b).parent)
            if dir_a == dir_b and dir_a != ".":
                continue

            score = min(1.0, round(pair.confidence * 0.7, 2))
            if score < 0.2:
                continue

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.LOW if score < 0.4 else Severity.MEDIUM,
                    score=score,
                    title=(
                        f"Hidden coupling: {Path(pair.file_a).name} ↔ "
                        f"{Path(pair.file_b).name} "
                        f"({pair.co_change_count} co-changes)"
                    ),
                    rule_id="avs_co_change",
                    description=(
                        f"{pair.file_a} and {pair.file_b} changed together in "
                        f"{pair.co_change_count} commits "
                        f"(confidence {pair.confidence:.0%}) but share no "
                        f"import relationship. This suggests a hidden logical "
                        f"dependency not visible in the import graph."
                    ),
                    file_path=Path(pair.file_a),
                    related_files=[Path(pair.file_b)],
                    fix=(
                        f"Investigate hidden coupling between "
                        f"{Path(pair.file_a).name} and {Path(pair.file_b).name}. "
                        f"Extract shared logic or make the dependency explicit."
                    ),
                    metadata={
                        "co_change_count": pair.co_change_count,
                        "confidence": pair.confidence,
                        "total_commits_a": pair.total_commits_a,
                        "total_commits_b": pair.total_commits_b,
                    },
                )
            )
        return findings
