"""Disk-backed persistence for the Architecture Graph."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from drift.arch_graph._models import ArchGraph

logger = logging.getLogger(__name__)


class ArchGraphStore:
    """JSON-backed store for :class:`ArchGraph`.

    Follows the same cache patterns as :class:`drift.cache.ParseCache`:
    schema-versioned, encoding-safe, graceful on corruption.
    """

    _FILENAME = "arch_graph.json"

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _path(self) -> Path:
        return self._cache_dir / self._FILENAME

    def save(self, graph: ArchGraph) -> None:
        """Persist *graph* to disk."""
        data = graph.to_dict()
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> ArchGraph | None:
        """Load the graph from disk.

        Returns *None* if the file is missing, corrupted, or has an
        incompatible schema version.
        """
        if not self._path.exists():
            return None

        try:
            raw = self._path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("arch_graph: ignoring corrupted cache file: %s", exc)
            return None

        if data.get("_schema_v") != ArchGraph._SCHEMA_VERSION:
            logger.debug(
                "arch_graph: schema version mismatch (got %s, want %s)",
                data.get("_schema_v"),
                ArchGraph._SCHEMA_VERSION,
            )
            return None

        try:
            return ArchGraph.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("arch_graph: failed to deserialize: %s", exc)
            return None
