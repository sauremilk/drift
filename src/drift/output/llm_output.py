"""Token-efficient LLM/AI-agent output format.

One line per finding, no ANSI colors, no Rich markup — optimized for
context windows of language models and coding agents.
"""

from __future__ import annotations

from drift import __version__
from drift.api_helpers import signal_abbrev
from drift.models import RepoAnalysis


def analysis_to_llm(analysis: RepoAnalysis) -> str:
    """Serialize analysis as a compact, token-efficient plain-text report."""
    lines: list[str] = []

    # Header
    repo_name = analysis.repo_path.name if analysis.repo_path else "unknown"
    lines.append(f"drift {__version__} · {repo_name} · {analysis.analyzed_at}")

    # Findings — one line each
    for f in analysis.findings:
        file_str = f.file_path.as_posix() if f.file_path else "unknown"
        line = f.start_line or 1
        abbrev = signal_abbrev(f.signal_type)
        sev = f.severity.value.upper()
        lines.append(f"[{abbrev}:{sev}] {file_str}:{line} — {f.title}")

    # Footer
    counts = {s: 0 for s in ("critical", "high", "medium", "low")}
    for f in analysis.findings:
        key = f.severity.value
        if key in counts:
            counts[key] += 1
    n = len(analysis.findings)
    score = round(analysis.drift_score * 100)
    lines.append(
        f"{n} findings · {counts['critical']} critical · {counts['high']} high · "
        f"{counts['medium']} medium · {counts['low']} low · score: {score}/100"
    )

    return "\n".join(lines)
