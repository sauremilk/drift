"""Baseline contract registry — loads contracts from drift.intent.baselines.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.intent.models import Contract

_BASELINES_FILENAME = "drift.intent.baselines.yaml"

# Cached baselines per path (avoids repeated YAML parsing)
_cache: dict[str, list[Contract]] = {}


def _locate_baselines(repo_path: Path) -> Path | None:
    """Find user-override baselines file in repo root (highest priority)."""
    candidate = repo_path / _BASELINES_FILENAME
    if candidate.exists():
        return candidate
    return None


def _get_baselines_text(repo_path: Path) -> str | None:
    """Return baselines YAML text: user-repo override takes priority, then package data."""
    path = _locate_baselines(repo_path)
    if path is not None:
        return path.read_text(encoding="utf-8")
    # Fallback: file shipped as package data under drift.intent.data
    try:
        from importlib.resources import files  # Python 3.9+

        return files("drift.intent.data").joinpath("baselines.yaml").read_text(
            encoding="utf-8"
        )
    except Exception:  # pragma: no cover
        return None


def load_baselines(
    repo_path: Path,
    *,
    category: str | None = None,
    _force_reload: bool = False,
) -> list[Contract]:
    """Load baseline contracts from the baselines YAML.

    Parameters
    ----------
    repo_path:
        Repository root (used to locate the YAML file).
    category:
        If given, return only contracts from this category.
    _force_reload:
        Bypass cache for testing.

    Returns
    -------
    list[Contract]
        Loaded baseline contracts.
    """
    import yaml  # type: ignore[import-untyped]

    cache_key = str(repo_path.resolve())
    if not _force_reload and cache_key in _cache:
        contracts = _cache[cache_key]
        if category:
            return [c for c in contracts if c.category == category]
        return list(contracts)

    raw = _get_baselines_text(repo_path)
    if raw is None:
        return []
    data: dict[str, Any] = yaml.safe_load(raw) or {}

    contracts: list[Contract] = []  # type: ignore[no-redef]
    for _cat_name, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            contracts.append(
                Contract(
                    id=item["id"],
                    description_technical=item["description_technical"],
                    description_human=item["description_human"],
                    category=item["category"],
                    severity=item["severity"],
                    auto_repair_eligible=item["auto_repair_eligible"],
                    source="baseline",
                )
            )

    _cache[cache_key] = contracts

    if category:
        return [c for c in contracts if c.category == category]
    return list(contracts)


def clear_cache() -> None:
    """Clear the baselines cache (for testing)."""
    _cache.clear()
