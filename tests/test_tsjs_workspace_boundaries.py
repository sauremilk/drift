from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.workspace_boundaries import (
    assign_ts_sources_to_workspace_packages,
    build_workspace_package_membership,
    discover_workspace_package_roots,
)


def test_discover_workspace_package_roots_from_root_package_json() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_workspace_boundaries"

    roots = discover_workspace_package_roots(repo_path)

    assert [root.as_posix() for root in roots] == [
        "packages/app",
        "packages/ui",
    ]


def test_assigns_each_fixture_source_to_exactly_one_package() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_workspace_boundaries"

    assignments = assign_ts_sources_to_workspace_packages(repo_path)

    assert assignments == {
        "vite.config.ts": "root",
        "packages/app/src/main.ts": "packages/app",
        "packages/ui/src/button.tsx": "packages/ui",
    }
    assert len(assignments) == 3
    assert len(set(assignments.values())) == 3


def test_exposes_package_membership_for_rule_modules() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_workspace_boundaries"

    membership = build_workspace_package_membership(repo_path)

    assert membership == {
        "root": {"vite.config.ts"},
        "packages/app": {"packages/app/src/main.ts"},
        "packages/ui": {"packages/ui/src/button.tsx"},
    }


def test_assignments_ignore_node_modules_sources(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name": "ws", "private": true, "workspaces": ["packages/*"]}\n',
        encoding="utf-8",
    )
    (tmp_path / "packages" / "app" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "app" / "src" / "main.ts").write_text(
        "export const main = 1;\n",
        encoding="utf-8",
    )

    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text(
        "export const vendor = 1;\n",
        encoding="utf-8",
    )

    assignments = assign_ts_sources_to_workspace_packages(tmp_path)

    assert assignments == {"packages/app/src/main.ts": "packages/app"}
