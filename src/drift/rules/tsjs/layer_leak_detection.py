"""Rule: one finding per direct TS/JS import violating ordered layer config."""

from __future__ import annotations

import json
from pathlib import Path

from drift.analyzers.typescript.import_graph import build_relative_import_graph

_RULE_ID = "layer-leak-detection"
_FILE_TO_LAYER_KEY = "file_to_layer"
_LAYER_ORDER_KEY = "layer_order"


def _load_rule_config(config_path: Path) -> tuple[list[str], dict[str, str]]:
    """Load ordered layers and repository-relative file-to-layer mapping."""
    if not config_path.is_file():
        return [], {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], {}

    if not isinstance(data, dict):
        return [], {}

    raw_layer_order = data.get(_LAYER_ORDER_KEY, [])
    raw_file_to_layer = data.get(_FILE_TO_LAYER_KEY, {})

    layer_order: list[str] = []
    if isinstance(raw_layer_order, list):
        for item in raw_layer_order:
            if isinstance(item, str):
                layer_order.append(item)

    file_to_layer: dict[str, str] = {}
    if isinstance(raw_file_to_layer, dict):
        for file_path, layer in raw_file_to_layer.items():
            if isinstance(file_path, str) and isinstance(layer, str):
                file_to_layer[file_path] = layer

    return layer_order, file_to_layer


def run_layer_leak_detection(repo_path: Path, config_path: Path) -> list[dict[str, str]]:
    """Emit one finding for each import that violates configured layer order.

    Layer order is interpreted from low index to high index. Imports are allowed
    within the same layer or from a lower index layer to a higher index layer.
    """
    layer_order, file_to_layer = _load_rule_config(config_path)
    if not layer_order:
        return []

    layer_to_index: dict[str, int] = {}
    for index, layer in enumerate(layer_order):
        if layer not in layer_to_index:
            layer_to_index[layer] = index

    import_graph = build_relative_import_graph(repo_path)

    findings: list[dict[str, str]] = []

    for source_file in sorted(import_graph):
        source_layer = file_to_layer.get(source_file)
        if source_layer is None or source_layer not in layer_to_index:
            continue

        source_index = layer_to_index[source_layer]

        for target_file in sorted(import_graph[source_file]):
            target_layer = file_to_layer.get(target_file)
            if target_layer is None or target_layer not in layer_to_index:
                continue

            target_index = layer_to_index[target_layer]
            if source_index <= target_index:
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
