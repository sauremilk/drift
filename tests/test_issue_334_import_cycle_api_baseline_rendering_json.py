from __future__ import annotations

import ast
from pathlib import Path

TARGET_MODULES = {
    "drift.api_helpers",
    "drift.baseline",
    "drift.finding_rendering",
    "drift.output.json_output",
}


def _module_to_file(module: str) -> Path:
    rel = Path(*module.split("."))
    return Path(__file__).resolve().parent.parent / "src" / f"{rel}.py"


def _extract_target_edges(module: str) -> set[str]:
    file_path = _module_to_file(module)
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    edges: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in TARGET_MODULES:
                    edges.add(alias.name)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module:
            continue
        if not node.module.startswith("drift"):
            continue

        if node.module in TARGET_MODULES:
            edges.add(node.module)

        for alias in node.names:
            dotted = f"{node.module}.{alias.name}"
            if dotted in TARGET_MODULES:
                edges.add(dotted)

    return edges


def _has_cycle(graph: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False

        visiting.add(node)
        for nxt in graph.get(node, set()):
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(dfs(node) for node in graph)


def test_issue_334_no_import_cycle_across_api_baseline_rendering_json() -> None:
    graph = {module: _extract_target_edges(module) for module in TARGET_MODULES}

    assert not _has_cycle(graph), (
        "Issue #334 regression: import cycle reintroduced among "
        "drift.api_helpers, drift.baseline, drift.finding_rendering, "
        "and drift.output.json_output"
    )
