"""YAML-based intent contract storage.

Stores contracts as a YAML list in ``.drift-intent.yaml`` in the project root.
Append-only — new contracts are added without overwriting existing ones.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.intent.models import IntentContract

INTENT_FILENAME = ".drift-intent.yaml"


def save_contract(contract: IntentContract, project_root: Path) -> Path:
    """Append an intent contract to the project's intent file.

    Parameters
    ----------
    contract:
        The contract to save.
    project_root:
        Path to the project root directory.

    Returns
    -------
    Path
        Path to the intent file.
    """
    import yaml  # type: ignore[import-untyped]

    intent_file = project_root / INTENT_FILENAME

    # Load existing contracts
    existing: list[dict[str, Any]] = []
    if intent_file.exists():
        raw = intent_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, list):
            existing = parsed

    # Append new contract
    existing.append(contract.to_dict())

    # Write back
    intent_file.write_text(
        yaml.dump(existing, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return intent_file


def load_contracts(project_root: Path) -> list[IntentContract]:
    """Load all intent contracts from the project's intent file.

    Parameters
    ----------
    project_root:
        Path to the project root directory.

    Returns
    -------
    list[IntentContract]
        All stored contracts, or empty list if no intent file exists.
    """
    import yaml

    intent_file = project_root / INTENT_FILENAME
    if not intent_file.exists():
        return []

    raw = intent_file.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, list):
        return []

    return [IntentContract.from_dict(entry) for entry in parsed]
