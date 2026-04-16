"""GitHub Actions annotation output format.

Emits findings as workflow commands that GitHub Actions renders as
inline annotations on PRs and in the Actions log.

Format reference:
https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/workflow-commands-for-github-actions#setting-a-warning-message
"""

from __future__ import annotations

from drift.models import RepoAnalysis, Severity

_LEVEL_MAP: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "notice",
    Severity.INFO: "notice",
}


def findings_to_github_annotations(analysis: RepoAnalysis) -> str:
    """Convert analysis findings to GitHub Actions annotation commands."""
    lines: list[str] = []
    for f in analysis.findings:
        level = _LEVEL_MAP.get(f.severity, "warning")
        file = f.file_path.as_posix() if f.file_path else "unknown"
        line = f.start_line or 1
        end_line = f.end_line or line
        title = f"{f.signal_type}: {f.title}"
        msg = f.description.replace("\n", "%0A").replace("\r", "")
        if f.fix:
            msg += " Fix: " + f.fix.replace("\n", "%0A").replace("\r", "")
        lines.append(
            f"::{level} file={file},line={line},endLine={end_line},title={title}::{msg}"
        )
    return "\n".join(lines)
