"""Finding grouping logic for --group-by output."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drift.models import Finding


def group_findings(
    findings: list[Finding],
    group_by: str,
) -> dict[str, list[Finding]]:
    """Group findings by the specified dimension.

    Supported values for *group_by*:
    - ``signal``    — by ``finding.signal_type``
    - ``severity``  — by ``finding.severity``
    - ``directory`` — by parent directory of ``finding.file_path``
    - ``module``    — by first path segment (top-level module)
    """
    groups: dict[str, list[Finding]] = defaultdict(list)

    for f in findings:
        key = _group_key(f, group_by)
        groups[key].append(f)

    # Sort groups by name for deterministic output
    return dict(sorted(groups.items()))


def _group_key(f: Finding, group_by: str) -> str:
    if group_by == "signal":
        return str(f.signal_type)
    if group_by == "severity":
        return f.severity.value
    if group_by == "directory":
        if f.file_path is None:
            return "(no file)"
        return PurePosixPath(f.file_path).parent.as_posix()
    if group_by == "module":
        if f.file_path is None:
            return "(no file)"
        parts = PurePosixPath(f.file_path).parts
        return parts[0] if parts else "(root)"
    return "(ungrouped)"
