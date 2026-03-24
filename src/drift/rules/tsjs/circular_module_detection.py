"""Rule: one finding per TS/JS file-level import cycle."""

from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph

_RULE_ID = "circular-module-detection"


def _canonicalize_cycle(cycle_nodes: list[str]) -> tuple[str, ...]:
    """Normalize a cycle by rotating it to a stable canonical representation."""
    if not cycle_nodes:
        return ()

    rotations = [
        tuple(cycle_nodes[index:] + cycle_nodes[:index])
        for index in range(len(cycle_nodes))
    ]
    return min(rotations)


def _find_cycles(import_graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all unique directed simple cycles with length >= 2."""
    seen_cycles: set[tuple[str, ...]] = set()

    for start_node in sorted(import_graph):
        stack: list[str] = []
        path_set: set[str] = set()

        def dfs(
            current_node: str,
            *,
            start_node: str = start_node,
            stack: list[str] = stack,
            path_set: set[str] = path_set,
        ) -> None:
            stack.append(current_node)
            path_set.add(current_node)

            for next_node in sorted(import_graph.get(current_node, set())):
                if next_node == start_node and len(stack) >= 2:
                    canonical = _canonicalize_cycle(stack.copy())
                    seen_cycles.add(canonical)
                    continue

                if next_node in path_set:
                    continue

                if next_node < start_node:
                    # Skip nodes lower than the start to avoid duplicate discovery.
                    continue

                dfs(next_node)

            path_set.remove(current_node)
            stack.pop()

        dfs(start_node)

    return [list(cycle) for cycle in sorted(seen_cycles)]


def run_circular_module_detection(repo_path: Path) -> list[dict[str, object]]:
    """Emit one finding for each detected file-level cycle of length >= 2."""
    import_graph = build_relative_import_graph(repo_path)

    findings: list[dict[str, object]] = []
    for cycle_nodes in _find_cycles(import_graph):
        findings.append(
            {
                "rule_id": _RULE_ID,
                "cycle_nodes": cycle_nodes,
                "cycle_length": len(cycle_nodes),
            }
        )

    return findings
