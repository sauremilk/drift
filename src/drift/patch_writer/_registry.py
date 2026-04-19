"""PatchWriter registry — maps edit_kind to the appropriate PatchWriter (ADR-076)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drift.patch_writer._base import PatchWriter

# Populated lazily so individual writers are only imported when needed.
_REGISTRY: dict[str, PatchWriter] | None = None


def _build_registry() -> dict[str, PatchWriter]:
    from drift.fix_intent import EDIT_KIND_ADD_DOCSTRING, EDIT_KIND_ADD_GUARD_CLAUSE
    from drift.patch_writer._add_docstring import AddDocstringWriter
    from drift.patch_writer._add_guard_clause import AddGuardClauseWriter

    return {
        EDIT_KIND_ADD_DOCSTRING: AddDocstringWriter(),
        EDIT_KIND_ADD_GUARD_CLAUSE: AddGuardClauseWriter(),
    }


def get_writer(edit_kind: str) -> PatchWriter | None:
    """Return the :class:`~drift.patch_writer._base.PatchWriter` for *edit_kind*.

    Returns ``None`` if no writer is registered for the given edit_kind.
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY.get(edit_kind)


def supported_edit_kinds() -> list[str]:
    """Return all edit_kind strings that have a registered PatchWriter."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return list(_REGISTRY.keys())
