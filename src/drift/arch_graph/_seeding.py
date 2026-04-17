"""Seed an ArchGraph from existing drift analysis data."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from drift.arch_graph._models import (
    ArchAbstraction,
    ArchDependency,
    ArchGraph,
    ArchModule,
)


def seed_graph(
    *,
    drift_map_result: dict[str, Any],
    version: str,
    module_scores: dict[str, dict[str, Any]] | None = None,
    parse_results: list[Any] | None = None,
    layer_boundaries: list[dict[str, Any]] | None = None,
) -> ArchGraph:
    """Build an :class:`ArchGraph` from existing drift data sources.

    Parameters
    ----------
    drift_map_result:
        Output of :func:`drift.api.drift_map` (must contain ``modules``
        and ``dependencies`` keys).
    version:
        Git commit SHA to stamp the graph.
    module_scores:
        Optional mapping of ``module_path -> {drift_score, signal_scores}``.
    parse_results:
        Optional list of :class:`~drift.models.ParseResult` objects.
        Exported functions and classes are extracted as abstractions.
    layer_boundaries:
        Optional list of boundary dicts with ``from``, ``deny_import`` keys
        (matching :class:`~drift.config._schema.LayerBoundary` shape).
    """
    modules = _build_modules(drift_map_result, module_scores)
    dependencies = _build_dependencies(drift_map_result, layer_boundaries)
    abstractions = _extract_abstractions(parse_results) if parse_results else []

    return ArchGraph(
        version=version,
        modules=modules,
        dependencies=dependencies,
        abstractions=abstractions,
        hotspots=[],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_modules(
    drift_map_result: dict[str, Any],
    module_scores: dict[str, dict[str, Any]] | None,
) -> list[ArchModule]:
    result: list[ArchModule] = []
    for mod in drift_map_result.get("modules", []):
        path = mod["path"]
        scores = (module_scores or {}).get(path, {})
        result.append(
            ArchModule(
                path=path,
                drift_score=scores.get("drift_score", 0.0),
                file_count=mod.get("files", 0),
                function_count=mod.get("functions", 0),
                signal_scores=scores.get("signal_scores", {}),
                languages=mod.get("languages", []),
            )
        )
    return result


def _build_dependencies(
    drift_map_result: dict[str, Any],
    layer_boundaries: list[dict[str, Any]] | None,
) -> list[ArchDependency]:
    result: list[ArchDependency] = []
    for dep in drift_map_result.get("dependencies", []):
        from_mod = dep["from"]
        to_mod = dep["to"]
        policy = _resolve_policy(from_mod, to_mod, layer_boundaries)
        result.append(
            ArchDependency(
                from_module=from_mod,
                to_module=to_mod,
                policy=policy,
            )
        )
    return result


def _resolve_policy(
    from_mod: str,
    to_mod: str,
    layer_boundaries: list[dict[str, Any]] | None,
) -> str | None:
    """Check if a dependency violates any layer boundary."""
    if not layer_boundaries:
        return None
    for boundary in layer_boundaries:
        from_pattern = boundary.get("from", "")
        deny_imports = boundary.get("deny_import", [])
        if fnmatch.fnmatch(from_mod, from_pattern) or from_mod == from_pattern:
            for denied in deny_imports:
                if fnmatch.fnmatch(to_mod, denied) or to_mod == denied:
                    return "forbidden"
    return None


def _extract_abstractions(
    parse_results: list[Any],
) -> list[ArchAbstraction]:
    """Extract exported functions and classes as abstractions."""
    abstractions: list[ArchAbstraction] = []

    for pr in parse_results:
        file_path_str = str(pr.file_path)
        # Derive module path from file path (remove file name, use parent dir)
        module_path = str(Path(pr.file_path).parent).replace("\\", "/")

        for func in getattr(pr, "functions", []):
            if not getattr(func, "is_exported", False):
                continue
            abstractions.append(
                ArchAbstraction(
                    symbol=func.name,
                    kind="function",
                    module_path=module_path,
                    file_path=file_path_str,
                    has_docstring=getattr(func, "has_docstring", False),
                    is_exported=True,
                )
            )

        for cls in getattr(pr, "classes", []):
            if not getattr(cls, "is_exported", False):
                continue
            abstractions.append(
                ArchAbstraction(
                    symbol=cls.name,
                    kind="class",
                    module_path=module_path,
                    file_path=file_path_str,
                    has_docstring=getattr(cls, "has_docstring", False),
                    is_exported=True,
                )
            )

    return abstractions
