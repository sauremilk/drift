"""Shared utilities for patch_writer modules (ADR-076).

Centralises the libcst availability guard so every writer module
can call ``_require_libcst()`` without duplicating the boilerplate.
"""

from __future__ import annotations

_LIBCST_MISSING_MSG = (
    "libcst is required for auto-patching. "
    "Install it with: pip install 'drift[autopatch]'"
)


def _require_libcst() -> None:
    """Raise ImportError with an actionable message if libcst is not installed."""
    try:
        import libcst  # noqa: F401
    except ImportError as exc:
        raise ImportError(_LIBCST_MISSING_MSG) from exc
