"""PR-comment output formatter for GitHub Pull Request comments.

Generates a compact, human-readable Markdown block suitable for posting
as a GitHub PR comment, Slack message, or issue update.
Key design constraints:
- Max 5 findings (default)
- Signal long-name via signal_registry
- Action text from generate_recommendation() or f.fix fallback
- No preflight diagnostics, module scores, or signal-coverage section
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from drift import __version__

if TYPE_CHECKING:
    from drift.models import Finding, RepoAnalysis

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "⚪",
}

_TREND_ARROW = {
    "worsening": "↑",
    "improving": "↓",
    "stable": "→",
}


def _trend_str(analysis: RepoAnalysis) -> str:
    trend = getattr(analysis, "trend", None)
    if trend is None or trend.delta is None:
        return "n/a"
    arrow = _TREND_ARROW.get(trend.direction, "→")
    sign = "+" if trend.delta >= 0 else ""
    return f"{arrow} {sign}{trend.delta:.1f}"


def _grade_label(analysis: RepoAnalysis) -> str:
    grade = getattr(analysis, "grade", None)
    if grade and len(grade) >= 2:
        return cast(str, grade[1])  # e.g. "healthy", "moderate drift", ...
    return ""


def _signal_long_name(signal_type: str) -> str:
    """Return human-readable signal name via signal_registry or fall back to abbrev."""
    try:
        from drift.signal_registry import get_meta

        meta = get_meta(signal_type)
        if meta:
            return cast(str, meta.signal_name)
    except (ImportError, AttributeError, KeyError, TypeError):
        pass
    return signal_type


def _action_text(finding: Finding) -> str:
    """Return short action text from recommender or f.fix fallback (max 90 chars)."""
    try:
        from drift.recommendations import generate_recommendation

        rec = generate_recommendation(finding)
        if rec:
            return cast(str, rec.title)[:90]
    except (ImportError, AttributeError, KeyError, TypeError):
        pass
    if finding.fix:
        return cast(str, finding.fix)[:90]
    return ""


def analysis_to_pr_comment(
    analysis: RepoAnalysis,
    *,
    max_findings: int = 5,
) -> str:
    """Generate a compact Markdown PR-comment from analysis results.

    Suitable for GitHub PR comments, Slack posts, and short issue updates.
    """
    from drift.models import Severity

    repo_name = analysis.repo_path.name
    date_str = analysis.analyzed_at.strftime("%Y-%m-%d")

    sev_emoji = _SEVERITY_EMOJI.get(analysis.severity.value, "⚪")
    sev_val = analysis.severity.value
    score = analysis.drift_score
    grade = _grade_label(analysis)
    grade_suffix = f" ({grade})" if grade else ""

    total = len(analysis.findings)
    high_count = sum(
        1
        for f in analysis.findings
        if f.severity in (Severity.CRITICAL, Severity.HIGH)
    )
    trend = _trend_str(analysis)

    lines: list[str] = []

    lines.append(f"## 🔍 Drift Analysis · `{repo_name}` · {date_str}")
    lines.append("")
    lines.append("| Score | Severity | Trend | Findings |")
    lines.append("|-------|----------|-------|----------|")
    lines.append(
        f"| **{score:.1f}**{grade_suffix}"
        f" | {sev_emoji} {sev_val}"
        f" | {trend}"
        f" | {total} total, {high_count} \u2265high |"
    )
    lines.append("")

    # Top findings table
    findings = sorted(
        analysis.findings,
        key=lambda f: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(
                f.severity.value, 5
            ),
            -(f.impact or 0),
        ),
    )
    shown = findings[:max_findings]

    if shown:
        lines.append("### Top Findings")
        lines.append("")
        lines.append("| # | Severity | Signal | Location | Action |")
        lines.append("|---|----------|--------|----------|--------|")
        for i, f in enumerate(shown, 1):
            sev_icon = _SEVERITY_EMOJI.get(f.severity.value, "⚪")
            location = f.file_path.as_posix() if f.file_path else ""
            if f.start_line:
                location += f":{f.start_line}"
            signal_name = _signal_long_name(f.signal_type)
            action = _action_text(f)
            lines.append(
                f"| {i} | {sev_icon} {f.severity.value}"
                f" | {signal_name}"
                f" | `{location}`"
                f" | {action} |"
            )
        lines.append("")

    shown_n = len(shown)
    if total > shown_n:
        lines.append(
            f"*{shown_n} of {total} findings shown"
            f" · [drift v{__version__}](https://github.com/mick-gsk/drift)*"
        )
    else:
        lines.append(
            f"*[drift v{__version__}](https://github.com/mick-gsk/drift)*"
        )
    lines.append("")

    return "\n".join(lines)
