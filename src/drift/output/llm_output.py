"""Token-efficient LLM/AI-agent output format.

One line per finding, no ANSI colors, no Rich markup — optimized for
context windows of language models and coding agents.
"""

from __future__ import annotations

from drift import __version__
from drift.api_helpers import signal_abbrev
from drift.models import RepoAnalysis

_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def analysis_to_llm(analysis: RepoAnalysis, *, max_findings: int = 50) -> str:
    """Serialize analysis as a compact, token-efficient plain-text report."""
    lines: list[str] = []

    # Header
    repo_name = analysis.repo_path.name if analysis.repo_path else "unknown"
    lines.append(f"drift {__version__} · {repo_name} · {analysis.analyzed_at}")

    findings = sorted(
        analysis.findings,
        key=lambda f: (
            _SEVERITY_ORDER.get(f.severity.value, 5),
            -(f.impact or 0),
        ),
    )

    shown = findings[: max(0, max_findings)]

    # Findings — one line each
    for f in shown:
        file_str = f.file_path.as_posix() if f.file_path else "unknown"
        line = f.start_line or 1
        abbrev = signal_abbrev(f.signal_type)
        sev = f.severity.value.upper()
        lines.append(f"[{abbrev}:{sev}] {file_str}:{line} — {f.title}")

    omitted = len(findings) - len(shown)
    if omitted > 0:
        lines.append(f"(+{omitted} more findings omitted - re-run with --max-findings to adjust)")

    # Footer
    counts = {s: 0 for s in ("critical", "high", "medium", "low")}
    for f in findings:
        key = f.severity.value
        if key in counts:
            counts[key] += 1
    n = len(findings)
    score = round(analysis.drift_score * 100)
    lines.append(
        f"{n} findings · {counts['critical']} critical · {counts['high']} high · "
        f"{counts['medium']} medium · {counts['low']} low · score: {score}/100"
    )

    return "\n".join(lines)
