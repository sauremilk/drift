"""Rich terminal output for Drift analysis results."""

from __future__ import annotations

import linecache
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType

# Brand accent: Deep Teal (slate/teal palette)
_TEAL = "rgb(13,148,136)"
_TEAL_BOLD = "bold rgb(13,148,136)"

if TYPE_CHECKING:
    from pathlib import Path

    from drift.recommendations import Recommendation
    from drift.timeline import RepoTimeline

# Colors per severity
_SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}

_SEVERITY_ICONS = {
    Severity.CRITICAL: "◉",
    Severity.HIGH: "◉",
    Severity.MEDIUM: "◎",
    Severity.LOW: "○",
    Severity.INFO: "○",
}

_SIGNAL_LABELS = {
    SignalType.PATTERN_FRAGMENTATION: "PFS",
    SignalType.ARCHITECTURE_VIOLATION: "AVS",
    SignalType.MUTANT_DUPLICATE: "MDS",
    SignalType.EXPLAINABILITY_DEFICIT: "EDS",
    SignalType.DOC_IMPL_DRIFT: "DIA",
    SignalType.TEMPORAL_VOLATILITY: "TVS",
    SignalType.SYSTEM_MISALIGNMENT: "SMS",
    SignalType.BROAD_EXCEPTION_MONOCULTURE: "BEM",
    SignalType.TEST_POLARITY_DEFICIT: "TPD",
    SignalType.GUARD_CLAUSE_DEFICIT: "GCD",
    SignalType.NAMING_CONTRACT_VIOLATION: "NBV",
    SignalType.BYPASS_ACCUMULATION: "BAT",
    SignalType.EXCEPTION_CONTRACT_DRIFT: "ECM",
    SignalType.CO_CHANGE_COUPLING: "CCC",
    SignalType.COHESION_DEFICIT: "COD",
    SignalType.MISSING_AUTHORIZATION: "MAZ",
    SignalType.INSECURE_DEFAULT: "ISD",
    SignalType.HARDCODED_SECRET: "HSC",
}


def _signal_label(signal_type: SignalType) -> str:
    """Return a stable signal label; fall back to canonical signal id."""
    return _SIGNAL_LABELS.get(signal_type, signal_type.value)


def _read_code_snippet(
    file_path: Path | None,
    start_line: int | None,
    *,
    end_line: int | None = None,
    context: int = 1,
    max_lines: int = 5,
    repo_root: Path | None = None,
) -> Text | None:
    """Read a short code snippet from a source file.

    Returns a Rich Text with line numbers, a ``→`` marker on the target
    line(s), and syntax-aware highlighting when possible.  Falls back to
    plain bold/dim rendering if the Syntax widget is unavailable.
    """
    if file_path is None or start_line is None:
        return None

    # Resolve absolute path
    if file_path.is_absolute():
        abs_path = file_path
    elif repo_root:
        abs_path = repo_root / file_path
    else:
        abs_path = file_path
    if not abs_path.is_file():
        return None

    highlight_end = end_line or start_line
    first = max(1, start_line - context)
    last = max(highlight_end + context, start_line + max_lines - 1)

    lines: list[tuple[int, str]] = []
    for lineno in range(first, last + 1):
        line = linecache.getline(str(abs_path), lineno)
        if not line and lineno > highlight_end:
            break
        lines.append((lineno, line.rstrip("\n\r")))

    if not lines:
        return None

    text = Text()
    gutter_width = len(str(lines[-1][0]))
    for lineno, content in lines:
        is_target = start_line <= lineno <= highlight_end
        marker = "→" if is_target else " "
        text.append(f"  {marker} {lineno:>{gutter_width}} │ ", style="dim")
        text.append(f"{content}\n", style="bold" if is_target else "dim")
    return text


def _score_bar(score: float, width: int = 20) -> Text:
    """Render a score as a colored bar."""
    filled = int(score * width)
    empty = width - filled

    if score >= 0.7:
        color = "red"
    elif score >= 0.4:
        color = "yellow"
    else:
        color = "green"

    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * empty, style="dim")
    bar.append(f" {score:.2f}", style="bold " + color)
    return bar


def _sparkline(values: list[float], width: int = 20) -> str:
    """Simple ASCII sparkline from a list of floats."""
    if not values:
        return ""
    chars = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    return "".join(chars[int((v - mn) / rng * (len(chars) - 1))] for v in values[-width:])


def render_summary(analysis: RepoAnalysis, console: Console | None = None) -> None:
    """Render the top-level analysis summary."""
    if console is None:
        console = Console()

    # Header
    console.print()
    header_color = _SEVERITY_COLORS.get(analysis.severity, "white")

    # Build trend suffix (ADR-005)
    trend = analysis.trend
    if trend and trend.direction != "baseline" and trend.delta is not None:
        arrow = (
            "↓" if trend.direction == "improving"
            else "↑" if trend.direction == "degrading"
            else "→"
        )
        delta_color = (
            _TEAL if trend.direction == "improving"
            else "red" if trend.direction == "degrading"
            else "dim"
        )
        trend_parts: tuple[tuple[str, str], ...] = (
            ("  ", ""),
            (f"Δ {trend.delta:+.3f} {arrow} {trend.direction}", delta_color),
        )
    else:
        trend_parts = (
            ("  — baseline", "dim"),
        )

    console.print(
        Panel(
            Text.assemble(
                ("DRIFT SCORE  ", "bold"),
                (f"{analysis.drift_score:.2f}", f"bold {header_color}"),
                *trend_parts,
                ("  │  ", "dim"),
                (f"{analysis.total_files} files", ""),
                ("  │  ", "dim"),
                (f"{analysis.total_functions} functions", ""),
                ("  │  ", "dim"),
                (f"AI: {analysis.ai_attributed_ratio:.0%}", ""),
                *(
                    (
                        (" (", "dim"),
                        (", ".join(analysis.ai_tools_detected), "dim italic"),
                        (")", "dim"),
                    )
                    if analysis.ai_tools_detected
                    else ()
                ),
                *(
                    (("  │  ", "dim"), (f"{analysis.suppressed_count} suppressed", "dim italic"))
                    if analysis.suppressed_count
                    else ()
                ),
                *(
                    (
                        ("  │  ", "dim"),
                        (f"{analysis.context_tagged_count} ctx-tagged", "dim italic"),
                    )
                    if analysis.context_tagged_count
                    else ()
                ),
                ("  │  ", "dim"),
                (f"{analysis.analysis_duration_seconds:.1f}s", "dim"),
                ("  │  ", "dim"),
                (
                    "DEGRADED" if analysis.is_degraded else "COMPLETE",
                    "bold yellow" if analysis.is_degraded else "bold green",
                ),
            ),
            title=f"[bold]drift analyze[/bold]  {analysis.repo_path}",
            border_style=header_color,
        ),
    )

    if analysis.is_degraded:
        causes = ", ".join(analysis.degradation_causes) or "unknown"
        components = ", ".join(analysis.degradation_components) or "unknown"
        console.print(
            f"  [bold yellow]Analysis degraded[/bold yellow]: causes={causes}; "
            f"components={components}",
        )

    # Trend sparkline (ADR-005)
    if trend and trend.recent_scores and trend.direction != "baseline":
        scores_str = " → ".join(f"{s:.3f}" for s in trend.recent_scores)
        depth = trend.history_depth
        sfx = "s" if depth != 1 else ""
        console.print(f"  [dim]Trend: {scores_str} ({depth} snapshot{sfx})[/dim]")
    elif trend and trend.direction == "baseline":
        console.print(
            "  [dim]⚠ Run drift analyze again after structural"
            " changes to establish trend.[/dim]",
        )


def render_module_table(analysis: RepoAnalysis, console: Console | None = None) -> None:
    """Render the module ranking table."""
    if console is None:
        console = Console()

    if not analysis.module_scores:
        console.print("[dim]No modules to display.[/dim]")
        return

    table = Table(title="Module Drift Ranking", show_lines=False, pad_edge=False)
    table.add_column("Module", style="bold", min_width=30)
    table.add_column("Score", justify="right", min_width=8)
    table.add_column("Bar", min_width=25)
    table.add_column("Findings", justify="right")
    table.add_column("Top Signal", min_width=10)

    for ms in analysis.module_scores[:15]:
        color = _SEVERITY_COLORS.get(ms.severity, "white")
        bar = _score_bar(ms.drift_score)

        top_signal = ""
        if ms.signal_scores:
            top = max(ms.signal_scores, key=lambda s: ms.signal_scores[s])
            top_signal = f"{_signal_label(top)} {ms.signal_scores[top]:.2f}"

        table.add_row(
            ms.path.as_posix() + "/",
            Text(f"{ms.drift_score:.2f}", style=color),
            bar,
            str(len(ms.findings)),
            top_signal,
        )

    console.print(table)


def _format_finding_detail(
    f: Finding,
    *,
    repo_root: Path | None = None,
    show_code: bool = True,
) -> Text:
    """Build the detail body for a single finding panel."""
    color = _SEVERITY_COLORS.get(f.severity, "white")
    signal_label = _signal_label(f.signal_type)
    text = Text()

    # Title: [SIGNAL] Description (score)
    text.append(f"[{signal_label}] {f.title} ({f.score:.2f})\n", style=f"bold {color}")

    # Primary location
    if f.file_path:
        loc = f.file_path.as_posix()
        if f.start_line:
            loc += f":{f.start_line}"
        text.append(f"  → {loc}\n", style="dim")

    # Code snippet with end_line support
    if show_code and f.file_path and f.start_line:
        snippet = _read_code_snippet(
            f.file_path,
            f.start_line,
            end_line=f.end_line,
            repo_root=repo_root,
        )
        if snippet is not None:
            text.append_text(snippet)

    # All related files (Opt-2: show them all, cap at 10 + remainder note)
    if f.related_files:
        shown = f.related_files[:10]
        for rf in shown:
            text.append(f"  → {rf.as_posix()}\n", style="dim")
        remainder = len(f.related_files) - len(shown)
        if remainder > 0:
            text.append(f"  … and {remainder} more\n", style="dim italic")

    # Description (first line only in compact view)
    first_line = f.description.splitlines()[0] if f.description else ""
    if first_line:
        text.append(f"  {first_line}\n", style="dim")

    # Next-action line — imperative, concrete
    if f.fix:
        text.append("  → Next: ", style=_TEAL_BOLD)
        text.append(f"{f.fix}\n", style=_TEAL)

    # Context tags (ADR-006)
    ctx_tags = f.metadata.get("context_tags")
    if ctx_tags:
        text.append(f"  [ctx: {', '.join(ctx_tags)}]\n", style="cyan italic")

    # Deliberate-pattern disambiguation (EPISTEMICS §1/§3)
    dpr = f.metadata.get("deliberate_pattern_risk")
    if dpr:
        text.append(f"  ⚠ {dpr}\n", style="dim italic")

    return text


def render_findings(
    findings: list[Finding],
    max_items: int = 20,
    console: Console | None = None,
    sort_by: str = "impact",
    *,
    repo_root: Path | None = None,
    show_code: bool = True,
) -> None:
    """Render a list of findings with fix recommendations and all locations."""
    if console is None:
        console = Console()

    if not findings:
        console.print("[green]No findings.[/green]")
        return

    if sort_by == "score":
        sorted_findings = sorted(findings, key=lambda f: f.score, reverse=True)
    else:
        # Sort by impact if available, fall back to score
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.impact if f.impact > 0 else f.score),
            reverse=True,
        )

    table = Table(title="Findings", show_lines=True)
    table.add_column("", width=2)
    table.add_column("Signal", min_width=5)
    table.add_column("Score", justify="right", min_width=6)
    table.add_column("Title / Details", min_width=50)

    for f in sorted_findings[:max_items]:
        icon = _SEVERITY_ICONS.get(f.severity, "?")
        color = _SEVERITY_COLORS.get(f.severity, "white")
        signal = _signal_label(f.signal_type)

        table.add_row(
            Text(icon, style=color),
            signal,
            Text(f"{f.score:.2f}", style=color),
            _format_finding_detail(f, repo_root=repo_root, show_code=show_code),
        )

    console.print(table)

    remaining = len(sorted_findings) - max_items
    if remaining > 0:
        console.print(f"[dim]... and {remaining} more findings[/dim]")


def render_module_detail(module: ModuleScore, console: Console | None = None) -> None:
    """Render detailed view for a single module."""
    if console is None:
        console = Console()

    color = _SEVERITY_COLORS.get(module.severity, "white")
    console.print()
    console.print(
        Panel(
            _format_module_detail(module),
            title=f"[bold]{module.path.as_posix()}/[/bold]",
            border_style=color,
        ),
    )


def _format_module_detail(module: ModuleScore) -> Text:
    """Build detail text for a module panel."""
    text = Text()
    text.append(f"Drift Score: {module.drift_score:.2f}", style="bold")
    text.append(f"  ({module.severity.value.upper()})\n\n", style="dim")

    for sig_type, score in sorted(module.signal_scores.items(), key=lambda x: x[1], reverse=True):
        label = _signal_label(sig_type)
        bar = "█" * int(score * 15) + "░" * (15 - int(score * 15))

        color = "green"
        if score >= 0.7:
            color = "red"
        elif score >= 0.4:
            color = "yellow"

        text.append(f"  {label}  ", style="bold")
        text.append(f"{bar}", style=color)
        text.append(f"  {score:.2f}\n")

    if module.findings:
        text.append("\nTop Findings:\n", style="bold")
        for f in sorted(module.findings, key=lambda x: x.score, reverse=True)[:5]:
            icon = _SEVERITY_ICONS.get(f.severity, "?")
            text.append(f"  {icon} ", style=_SEVERITY_COLORS.get(f.severity, "white"))
            text.append(f"{f.title}\n")

    return text


def render_full_report(
    analysis: RepoAnalysis,
    console: Console | None = None,
    sort_by: str = "impact",
    max_findings: int = 20,
    *,
    show_code: bool = True,
) -> None:
    """Render the complete analysis report."""
    if console is None:
        console = Console()

    render_summary(analysis, console)
    console.print()
    render_module_table(analysis, console)
    console.print()
    render_findings(
        analysis.findings,
        max_items=max_findings,
        console=console,
        sort_by=sort_by,
        repo_root=analysis.repo_path,
        show_code=show_code,
    )

    # Interpretation guidance footer
    console.print()
    console.print(
        Panel(
            "[dim]The drift score measures structural entropy, not code quality. "
            "A rising score signals coherence loss — but temporary increases "
            "during migrations or refactorings are expected.\n"
            "Deliberate polymorphism (Strategy, Adapter, Plugin patterns) can "
            "trigger MDS/PFS findings that reflect correct design, not erosion.\n"
            "Use [bold]drift trend[/bold] to track deltas over time. "
            "Interpret single snapshots with caution.[/dim]",
            title="[dim bold]Interpretation[/dim bold]",
            border_style=_TEAL,
        ),
    )


# ---------------------------------------------------------------------------
# Timeline rendering
# ---------------------------------------------------------------------------


def render_timeline(
    timeline: RepoTimeline,
    console: Console | None = None,
) -> None:
    """Render the drift timeline showing *when* and *why* drift began."""
    if console is None:
        console = Console()

    if not timeline.module_timelines:
        console.print("[dim]No timeline data — no modules with findings.[/dim]")
        return

    # AI burst summary
    if timeline.ai_burst_periods:
        console.print()
        console.print("[bold]AI Commit Bursts[/bold]")
        for burst in timeline.ai_burst_periods:
            span = burst.end_date - burst.start_date
            console.print(
                f"  [red]●[/red] {burst.start_date} → {burst.end_date} "
                f"({span.days + 1}d): "
                f"[bold]{burst.ai_commit_count}[/bold] AI commits "
                f"/ {burst.commit_count} total, "
                f"{len(burst.files_affected)} files",
            )
        console.print()

    # Per-module timelines
    table = Table(title="Module Drift Timeline", show_lines=True)
    table.add_column("Module", style="bold", min_width=20)
    table.add_column("Clean Until", min_width=12)
    table.add_column("Drift Started", min_width=12)
    table.add_column("Trigger Commits", justify="right")
    table.add_column("AI Burst?", min_width=8)
    table.add_column("Score", justify="right")

    for mt in timeline.module_timelines[:15]:
        clean = str(mt.clean_until) if mt.clean_until else "[dim]—[/dim]"
        started = f"[red]{mt.drift_started}[/red]" if mt.drift_started else "[dim]—[/dim]"
        triggers = str(len(mt.trigger_commits))
        burst_label = "[red]yes[/red]" if mt.ai_burst else "[dim]no[/dim]"
        color = (
            "red" if mt.current_score >= 0.6 else ("yellow" if mt.current_score >= 0.3 else "green")
        )
        score = f"[{color}]{mt.current_score:.2f}[/{color}]"

        table.add_row(mt.module_path, clean, started, triggers, burst_label, score)

    console.print(table)

    # Detailed trigger commits for top 3 drifting modules
    console.print()
    for mt in timeline.module_timelines[:3]:
        if not mt.trigger_commits:
            continue
        console.print(f"[bold]{mt.module_path}/[/bold] — trigger commits:")
        for evt in mt.trigger_commits[:5]:
            ai_tag = " [red](AI)[/red]" if evt.is_ai else ""
            console.print(
                f"  {evt.date}  "
                f"[dim]{evt.commit_hash or '?'}[/dim]  "
                f"{evt.author or '?'}{ai_tag}  "
                f"{evt.description}",
            )
        remaining = len(mt.trigger_commits) - 5
        if remaining > 0:
            console.print(f"  [dim]... +{remaining} more[/dim]")
        console.print()


# ---------------------------------------------------------------------------
# Recommendations rendering
# ---------------------------------------------------------------------------


def render_recommendations(
    recommendations: list[Recommendation],
    console: Console | None = None,
) -> None:
    """Render actionable recommendations."""
    if console is None:
        console = Console()

    if not recommendations:
        console.print("[green]No recommendations — codebase is clean![/green]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]{len(recommendations)} Recommendations[/bold]",
            border_style=_TEAL,
        ),
    )

    impact_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    effort_labels = {
        "low": "[green]low[/green]",
        "medium": "[yellow]med[/yellow]",
        "high": "[red]high[/red]",
    }

    for i, rec in enumerate(recommendations, 1):
        impact_icon = impact_icons.get(rec.impact, "?")
        effort_label = effort_labels.get(rec.effort, rec.effort)
        file_hint = f"  [dim]{rec.file_path.as_posix()}[/dim]" if rec.file_path else ""

        console.print(f"  {impact_icon} [bold]{i}. {rec.title}[/bold]{file_hint}")
        console.print(f"     {rec.description}")
        console.print(f"     Effort: {effort_label}  |  Impact: {rec.impact}")
        console.print()


# ---------------------------------------------------------------------------
# Trend chart rendering
# ---------------------------------------------------------------------------


def render_trend_chart(
    snapshots: list[dict],
    width: int = 60,
    console: Console | None = None,
) -> None:
    """Render an ASCII trend chart of drift scores over time."""
    if console is None:
        console = Console()

    if len(snapshots) < 2:
        console.print("[dim]Need at least 2 snapshots for a chart.[/dim]")
        return

    scores = [s["drift_score"] for s in snapshots]
    dates = [s["timestamp"][:10] for s in snapshots]

    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score if max_score != min_score else 0.1

    # Chart height
    height = 12
    chart_width = min(width, len(scores))

    # Resample if we have more snapshots than chart width
    if len(scores) > chart_width:
        step = len(scores) / chart_width
        sampled_scores = [scores[int(i * step)] for i in range(chart_width)]
        sampled_dates = [dates[int(i * step)] for i in range(chart_width)]
    else:
        sampled_scores = scores
        sampled_dates = dates
        chart_width = len(scores)

    console.print()
    console.print("[bold]Drift Score Trend[/bold]")
    console.print()

    # Render chart rows top-down
    for row in range(height, -1, -1):
        threshold = min_score + (row / height) * score_range
        label = f"{threshold:.2f} │"
        line = []
        for s in sampled_scores:
            normalized = (s - min_score) / score_range
            bar_height = normalized * height
            if bar_height >= row:
                if s >= 0.6:
                    line.append("[red]█[/red]")
                elif s >= 0.3:
                    line.append("[yellow]█[/yellow]")
                else:
                    line.append("[green]█[/green]")
            else:
                line.append(" ")
        console.print(f"  {label}{''.join(line)}")

    # X-axis
    axis = "─" * chart_width
    console.print(f"       └{axis}")

    # Date labels
    if len(sampled_dates) >= 2:
        first_date = sampled_dates[0]
        last_date = sampled_dates[-1]
        padding = chart_width - len(first_date) - len(last_date)
        if padding > 0:
            console.print(f"        {first_date}{' ' * padding}{last_date}")
        else:
            console.print(f"        {first_date}  ...  {last_date}")
    console.print()
