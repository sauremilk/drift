from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph


def test_build_relative_import_graph_resolves_relative_ts_and_tsx() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_graph_relative"

    graph = build_relative_import_graph(repo_path)

    edges = {
        (source, target)
        for source, targets in graph.items()
        for target in targets
    }

    expected_edges = {
        ("app.ts", "lib/util.ts"),
        ("app.ts", "components/button.tsx"),
        ("app.ts", "components/index.ts"),
        ("components/index.ts", "components/button.tsx"),
        ("components/button.tsx", "lib/util.ts"),
        ("lib/util.ts", "components/button.tsx"),
    }

    assert edges == expected_edges
