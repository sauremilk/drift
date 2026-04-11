"""Shared path utilities for TypeScript analyzers."""

from __future__ import annotations

from pathlib import Path


def relative_to_or_none(path: Path, base: Path) -> Path | None:
    """Return ``path.relative_to(base)`` or ``None`` when path is outside base."""
    if path == base or base in path.parents:
        return path.relative_to(base)
    return None
