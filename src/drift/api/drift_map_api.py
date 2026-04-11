"""Drift-map endpoint — lightweight module/dependency map."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def drift_map(
    path: str | Path = ".",
    *,
    target_path: str | None = None,
    max_modules: int = 50,
) -> dict[str, Any]:
    """Return a lightweight module/dependency map for a repository path."""
    repo_path = Path(path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        return {
            "status": "error",
            "error_code": "DRIFT-2001",
            "message": f"Repository path not found: {repo_path}",
        }

    scan_root = repo_path
    if target_path:
        candidate = (repo_path / target_path).resolve()
        if not candidate.exists() or not candidate.is_dir():
            return {
                "status": "ok",
                "modules": [],
                "dependencies": [],
                "stats": {
                    "total_files": 0,
                    "total_modules": 0,
                    "total_dependencies": 0,
                },
                "agent_instruction": "No files found in target_path; widen scope or verify path.",
            }
        scan_root = candidate

    py_files = [
        p
        for p in scan_root.rglob("*.py")
        if ".venv" not in p.parts and "__pycache__" not in p.parts
    ]

    module_stats: dict[str, dict[str, Any]] = {}
    dependencies: set[tuple[str, str]] = set()

    for file_path in py_files:
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = file_path.relative_to(repo_path)
        module = rel.parent.as_posix() if rel.parent.as_posix() != "." else "<root>"
        stats = module_stats.setdefault(
            module,
            {
                "path": module,
                "files": 0,
                "functions": 0,
                "classes": 0,
                "lines": 0,
                "languages": ["python"],
            },
        )
        stats["files"] += 1
        stats["lines"] += len(source.splitlines())

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stats["functions"] += 1
            elif isinstance(node, ast.ClassDef):
                stats["classes"] += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name.split(".")[0]
                    if imported and imported in module_stats:
                        dependencies.add((module, imported))
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = node.module.split(".")[0]
                if imported and imported in module_stats:
                    dependencies.add((module, imported))

    modules = sorted(module_stats.values(), key=lambda item: str(item["path"]))
    if max_modules > 0:
        modules = modules[:max_modules]
    deps = [
        {"from": src, "to": dst}
        for src, dst in sorted(dependencies)
        if src != dst
    ]

    return {
        "status": "ok",
        "modules": modules,
        "dependencies": deps,
        "stats": {
            "total_files": len(py_files),
            "total_modules": len(modules),
            "total_dependencies": len(deps),
        },
        "agent_instruction": (
            "Use modules to identify architectural hotspots; prioritize high-file modules "
            "and dense dependency edges for focused remediation."
        ),
    }
