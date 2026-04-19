"""PatchWriter subpackage — source-code auto-patching for high-confidence findings (ADR-076).

Usage::

    from drift.patch_writer import get_writer, PatchResult, PatchResultStatus

    writer = get_writer("add_docstring")
    if writer and writer.can_write(finding):
        result = writer.generate_patch(finding, source)

Requires the ``drift[autopatch]`` extra (``pip install drift[autopatch]``).
"""

from drift.patch_writer._base import PatchResult, PatchResultStatus, PatchWriter
from drift.patch_writer._registry import get_writer, supported_edit_kinds

__all__ = [
    "PatchWriter",
    "PatchResult",
    "PatchResultStatus",
    "get_writer",
    "supported_edit_kinds",
]
