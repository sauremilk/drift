"""Rich terminal output for Drift analysis results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType

# Colors per severity
_SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}

_SEVERITY_ICONS = {
    Severity.CRITICAL: "●",
    Severity.HIGH: "◉",
    Severity.MEDIUM: "○",
    Severity.LOW: "◌",
    Severity.INFO: "·",
}

_SIGNAL_LABELS = {
    SignalType.PATTERN_FRAGMENTATION: "PFS",
    SignalType.ARCHITECTURE_VIOLATION: "AVS",
    SignalType.MUTANT_DUPLICATE: "MDS",
    SignalType.EXPLAINABILITY_DEFICIT: "EDS",
    SignalType.DOC_IMPL_DRIFT: "DIA",
    SignalType.TEMPORAL_VOLATILITY: "TVS",
    SignalType.SYSTEM_MISALIGNMENT: "SMS",
}


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
    return "".join(
        chars[int((v - mn) / rng * (len(chars) - 1))] for v in values[-width:]
    )


def render_summary(analysis: RepoAnalysis, console: Console | None = None) -> None:
    """Render the top-level analysis summary."""
    if console is None:
        console = Console()

    # Header
    console.print()
    header_color = _SEVERITY_COLORS.get(analysis.severity, "white")
    console.print(
        Panel(
            Text.assemble(
                ("DRIFT SCORE  ", "bold"),
                (f"{analysis.drift_score:.2f}", f"bold {header_color}"),
                ("  │  ", "dim"),
                (f"{analysis.total_files} files", ""),
                ("  │  ", "dim"),
                (f"{analysis.total_functions} functions", ""),
                ("  │  ", "dim"),
                (f"AI: {analysis.ai_attributed_ratio:.0%}", ""),
                ("  │  ", "dim"),
                (f"{analysis.analysis_duration_seconds:.1f}s", "dim"),
            ),
            title=f"[bold]drift analyze[/bold]  {analysis.repo_path}",
            border_style=header_color,
        )
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
            top_signal = f"{_SIGNAL_LABELS.get(top, '?')} {ms.signal_scores[top]:.2f}"

        table.add_row(
            ms.path.as_posix() + "/",
            Text(f"{ms.drift_score:.2f}", style=color),
            bar,
            str(len(ms.findings)),
            top_signal,
        )

    console.print(table)


def render_findings(
    findings: list[Finding],
    max_items: int = 20,
    console: Console | None = None,
) -> None:
    """Render a list of findings."""
    if console is None:
        console = Console()

    if not findings:
        console.print("[green]No findings.[/green]")
        return

    sorted_findings = sorted(findings, key=lambda f: f.score, reverse=True)

    table = Table(title="Findings", show_lines=True)
    table.add_column("", width=2)
    table.add_column("Signal", min_width=5)
    table.add_column("Score", justify="right", min_width=6)
    table.add_column("Title", min_width=40)
    table.add_column("Location", min_width=20)

    for f in sorted_findings[:max_items]:
        icon = _SEVERITY_ICONS.get(f.severity, "?")
        color = _SEVERITY_COLORS.get(f.severity, "white")
        signal = _SIGNAL_LABELS.get(f.signal_type, "?")

        location = ""
        if f.file_path:
            location = f.file_path.as_posix()
            if f.start_line:
                location += f":{f.start_line}"

        table.add_row(
            Text(icon, style=color),
            signal,
            Text(f"{f.score:.2f}", style=color),
            f.title,
            location,
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
        )
    )


def _format_module_detail(module: ModuleScore) -> Text:
    """Build detail text for a module panel."""
    text = Text()
    text.append(f"Drift Score: {module.drift_score:.2f}", style="bold")
    text.append(f"  ({module.severity.value.upper()})\n\n", style="dim")

    for sig_type, score in sorted(
        module.signal_scores.items(), key=lambda x: x[1], reverse=True
    ):
        label = _SIGNAL_LABELS.get(sig_type, "???")
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


def render_full_report(analysis: RepoAnalysis, console: Console | None = None) -> None:
    """Render the complete analysis report."""
    if console is None:
        console = Console()

    render_summary(analysis, console)
    console.print()
    render_module_table(analysis, console)
    console.print()
    render_findings(analysis.findings, console=console)
