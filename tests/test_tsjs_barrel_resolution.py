from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph


def test_build_relative_import_graph_resolves_one_hop_barrel_index() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_barrel_resolution"

    graph = build_relative_import_graph(repo_path)

    edges = {
        (source, target)
        for source, targets in graph.items()
        for target in targets
    }

    assert ("src/app.ts", "src/button.tsx") in edges
    assert all(not target.endswith("index.ts") for _, target in edges)
