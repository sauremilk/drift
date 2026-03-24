"""Rule: one finding per forbidden direct cross-package TS/JS import."""

from __future__ import annotations

import json
from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph
from drift.analyzers.typescript.workspace_boundaries import (
    assign_ts_sources_to_workspace_packages,
)

_ALLOWED_IMPORT_PAIRS_KEY = "allowed_package_import_pairs"
_RULE_ID = "cross-package-import-ban"


def _load_allowed_package_import_pairs(config_path: Path) -> set[tuple[str, str]]:
    """Load directed allowed package pairs from JSON config.

    Accepted formats per item:
    - ["source_package", "target_package"]
    - {"source_package": "...", "target_package": "..."}
    """
    if not config_path.is_file():
        return set()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    raw_pairs = data.get(_ALLOWED_IMPORT_PAIRS_KEY, []) if isinstance(data, dict) else []
    if not isinstance(raw_pairs, list):
        return set()

    allowed_pairs: set[tuple[str, str]] = set()
    for item in raw_pairs:
        if (
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], str)
        ):
            allowed_pairs.add((item[0], item[1]))
            continue

        if isinstance(item, dict):
            source_package = item.get("source_package")
            target_package = item.get("target_package")
            if isinstance(source_package, str) and isinstance(target_package, str):
                allowed_pairs.add((source_package, target_package))

    return allowed_pairs


def run_cross_package_import_ban(
    repo_path: Path,
    config_path: Path,
) -> list[dict[str, str]]:
    """Emit one finding for each forbidden direct import crossing packages."""
    file_to_package = assign_ts_sources_to_workspace_packages(repo_path)
    import_graph = build_relative_import_graph(repo_path)
    allowed_pairs = _load_allowed_package_import_pairs(config_path)

    findings: list[dict[str, str]] = []

    for source_file in sorted(import_graph):
        source_package = file_to_package.get(source_file)
        if source_package is None:
            continue

        for target_file in sorted(import_graph[source_file]):
            target_package = file_to_package.get(target_file)
            if target_package is None:
                continue

            if source_package == target_package:
                continue

            if (source_package, target_package) in allowed_pairs:
                continue

            findings.append(
                {
                    "rule_id": _RULE_ID,
                    "source_file": source_file,
                    "target_file": target_file,
                    "source_package": source_package,
                    "target_package": target_package,
                }
            )

    return findings
