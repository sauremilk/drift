"""CSV output formatter for lightweight tabular integrations."""

from __future__ import annotations

import csv
import io

from drift.api_helpers import signal_abbrev
from drift.models import Finding, RepoAnalysis
from drift.signal_registry import get_meta


def _finding_sort_key(finding: Finding) -> tuple[float, str, str, int, int]:
    """Stable ordering key for deterministic CSV output."""
    return (
        -float(finding.impact),
        finding.signal_type,
        finding.file_path.as_posix() if finding.file_path else "",
        int(finding.start_line or 0),
        int(finding.end_line or 0),
    )


def _format_score(score: float) -> str:
    """Render scores with stable precision and without trailing zeros."""
    return f"{score:.3f}".rstrip("0").rstrip(".")


def analysis_to_csv(analysis: RepoAnalysis) -> str:
    """Serialize findings to CSV with one finding per row."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["signal", "signal_label", "severity", "score", "title", "file", "start_line", "end_line"]
    )

    ranked_findings = sorted(analysis.findings, key=_finding_sort_key)
    for finding in ranked_findings:
        meta = get_meta(finding.signal_type)
        signal_label = meta.signal_name if meta else finding.signal_type
        writer.writerow(
            [
                signal_abbrev(finding.signal_type),
                signal_label,
                finding.severity.value,
                _format_score(finding.score),
                finding.title,
                finding.file_path.as_posix() if finding.file_path else "",
                finding.start_line if finding.start_line is not None else "",
                finding.end_line if finding.end_line is not None else "",
            ],
        )

    return buffer.getvalue()
