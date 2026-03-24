"""Rule: one finding per direct ui-to-infra TS/JS import."""

from __future__ import annotations

import json
from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph

_RULE_ID = "ui-to-infra-import-ban"
_FILE_TO_LAYER_KEY = "file_to_layer"


def _load_file_to_layer_mapping(config_path: Path) -> dict[str, str]:
    """Load repository-relative file-to-layer mapping from JSON config."""
    if not config_path.is_file():
        return {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    raw_mapping = data.get(_FILE_TO_LAYER_KEY, {}) if isinstance(data, dict) else {}
    if not isinstance(raw_mapping, dict):
        return {}

    file_to_layer: dict[str, str] = {}
    for file_path, layer in raw_mapping.items():
        if isinstance(file_path, str) and isinstance(layer, str):
            file_to_layer[file_path] = layer

    return file_to_layer


def run_ui_to_infra_import_ban(repo_path: Path, config_path: Path) -> list[dict[str, str]]:
    """Emit one finding for each direct import from layer ui to layer infra."""
    file_to_layer = _load_file_to_layer_mapping(config_path)
    import_graph = build_relative_import_graph(repo_path)

    findings: list[dict[str, str]] = []

    for source_file in sorted(import_graph):
        source_layer = file_to_layer.get(source_file)
        if source_layer != "ui":
            continue

        for target_file in sorted(import_graph[source_file]):
            target_layer = file_to_layer.get(target_file)
            if target_layer != "infra":
                continue

            findings.append(
                {
                    "rule_id": _RULE_ID,
                    "source_file": source_file,
                    "target_file": target_file,
                    "source_layer": source_layer,
                    "target_layer": target_layer,
                }
            )

    return findings
