from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph


def test_build_relative_import_graph_resolves_one_hop_barrel_index() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_barrel_resolution"

    graph = build_relative_import_graph(repo_path)

    edges = {(source, target) for source, targets in graph.items() for target in targets}

    assert ("src/app.ts", "src/button.tsx") in edges
    assert all(not target.endswith("index.ts") for _, target in edges)


def test_build_relative_import_graph_resolves_one_hop_barrel_index_tsx() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_barrel_resolution"

    graph = build_relative_import_graph(repo_path)

    edges = {(source, target) for source, targets in graph.items() for target in targets}

    assert ("src/app_tsx.ts", "src/view/card.tsx") in edges
    assert all(not target.endswith("index.tsx") for _, target in edges)


def test_build_relative_import_graph_ignores_node_modules_sources(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "dep.ts").write_text("export const dep = 1;", encoding="utf-8")
    (tmp_path / "src" / "app.ts").write_text(
        "import { dep } from './dep';\nconsole.log(dep);\n",
        encoding="utf-8",
    )

    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text(
        "import { missing } from './missing';\nconsole.log(missing);\n",
        encoding="utf-8",
    )

    graph = build_relative_import_graph(tmp_path)

    assert "src/app.ts" in graph
    assert "src/dep.ts" not in graph
    assert all(not source.startswith("node_modules/") for source in graph)
