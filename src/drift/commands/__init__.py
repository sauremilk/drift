"""Drift CLI subcommands — each file registers one Click command."""

from __future__ import annotations

import locale
import sys
from typing import Any, cast

from rich.console import Console


def _stream_supports_unicode(stream: Any) -> bool:
    """Return True when the target stream can safely encode Drift's rich symbols."""
    encoding = getattr(stream, "encoding", None) or locale.getpreferredencoding(False)
    if not encoding:
        return False
    try:
        "╭╰│→✓⚠".encode(str(encoding))
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def make_console(*, stderr: bool = False, no_color: bool = False) -> Console:
    """Build a shared console with ASCII fallback for legacy Windows encodings."""
    stream = sys.stderr if stderr else sys.stdout
    unicode_ok = _stream_supports_unicode(stream)
    built = Console(
        stderr=stderr,
        no_color=no_color,
        safe_box=not unicode_ok,
        emoji=unicode_ok,
    )
    console_any = cast(Any, built)
    console_any._drift_ascii_only = not unicode_ok
    return built


console = make_console()
