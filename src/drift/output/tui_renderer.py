"""Interactive TUI for Drift analysis results.

Requires the ``textual`` optional dependency::

    pip install drift-analyzer[tui]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static

if TYPE_CHECKING:
    from drift.models import ModuleScore, RepoAnalysis

# Severity → color mapping
_SCORE_STYLE = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "green",
    "info": "dim",
}


def _severity_label(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "medium"
    if score >= 0.2:
        return "low"
    return "info"


def _score_bar(score: float, width: int = 20) -> str:
    """Render a visual bar for a score value."""
    filled = int(score * width)
    return "█" * filled + "░" * (width - filled)


class DriftVisualizeApp(App):
    """Interactive TUI dashboard for drift analysis results."""

    TITLE = "Drift — Architecture Health"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
    }

    #left-pane {
        height: 100%;
    }

    #right-pane {
        height: 100%;
        overflow-y: auto;
    }

    #summary-bar {
        dock: top;
        height: 3;
        background: $surface;
        padding: 0 2;
        content-align: center middle;
    }

    #module-table {
        height: 1fr;
    }

    #detail-panel {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
    }

    .severity-critical { color: red; text-style: bold; }
    .severity-high { color: red; }
    .severity-medium { color: yellow; }
    .severity-low { color: green; }
    .severity-info { color: $text-muted; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "deselect", "Back"),
    ]

    def __init__(self, analysis: RepoAnalysis) -> None:
        super().__init__()
        self._analysis = analysis
        self._modules: list[ModuleScore] = sorted(
            analysis.module_scores,
            key=lambda m: m.drift_score,
            reverse=True,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        summary = self._build_summary()
        yield Static(summary, id="summary-bar")
        with Horizontal():
            with Vertical(id="left-pane"):
                yield DataTable(id="module-table", cursor_type="row")
            with Vertical(id="right-pane"):
                yield Static(
                    "[dim]Select a module to see findings.[/dim]",
                    id="detail-panel",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Populate the module table on startup."""
        table = self.query_one("#module-table", DataTable)
        table.add_columns("Module", "Score", "Bar", "Sev", "Findings", "Files")
        for ms in self._modules:
            sev = _severity_label(ms.drift_score)
            style = _SCORE_STYLE.get(sev, "")
            table.add_row(
                str(ms.path),
                f"[{style}]{ms.drift_score:.3f}[/]",
                f"[{style}]{_score_bar(ms.drift_score, 15)}[/]",
                f"[{style}]{sev.upper()}[/]",
                str(len(ms.findings)),
                str(ms.file_count),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show findings for selected module."""
        idx = event.cursor_row
        if idx < 0 or idx >= len(self._modules):
            return
        ms = self._modules[idx]
        detail = self._build_detail(ms)
        self.query_one("#detail-panel", Static).update(detail)

    def action_deselect(self) -> None:
        """Clear the detail panel."""
        self.query_one("#detail-panel", Static).update(
            "[dim]Select a module to see findings.[/dim]"
        )

    def _build_summary(self) -> str:
        """Build the top summary bar text."""
        a = self._analysis
        sev = _severity_label(a.drift_score)
        style = _SCORE_STYLE.get(sev, "")
        return (
            f"[bold]Drift Score:[/bold] [{style}]{a.drift_score:.3f}[/]  "
            f"│  Modules: {len(a.module_scores)}  "
            f"│  Findings: {len(a.findings)}  "
            f"│  Files: {a.total_files}"
        )

    def _build_detail(self, ms: ModuleScore) -> str:
        """Build the finding detail panel for a module."""
        from drift.models import Severity

        sev = _severity_label(ms.drift_score)
        style = _SCORE_STYLE.get(sev, "")
        lines = [
            f"[bold]{ms.path}[/bold]",
            f"Score: [{style}]{ms.drift_score:.3f}[/]  │  "
            f"Files: {ms.file_count}  │  Functions: {ms.function_count}  │  "
            f"AI ratio: {ms.ai_ratio:.0%}",
            "",
        ]

        # Signal breakdown
        if ms.signal_scores:
            lines.append("[bold]Signal Scores:[/bold]")
            for sig, score in sorted(
                ms.signal_scores.items(), key=lambda x: x[1], reverse=True
            ):
                if score > 0:
                    sig_sev = _severity_label(score)
                    sig_style = _SCORE_STYLE.get(sig_sev, "")
                    bar = _score_bar(score, 10)
                    lines.append(
                        f"  [{sig_style}]{bar}[/] {score:.3f}  {sig}"
                    )
            lines.append("")

        # Findings list
        if ms.findings:
            lines.append(f"[bold]Findings ({len(ms.findings)}):[/bold]")
            sev_order = {
                Severity.CRITICAL: 0,
                Severity.HIGH: 1,
                Severity.MEDIUM: 2,
                Severity.LOW: 3,
                Severity.INFO: 4,
            }
            for f in sorted(
                ms.findings,
                key=lambda x: sev_order.get(x.severity, 5),
            ):
                f_style = _SCORE_STYLE.get(f.severity.value, "")
                loc = f"{f.file_path}:{f.start_line}" if f.start_line else str(f.file_path or "?")
                lines.append(
                    f"  [{f_style}]● {f.severity.value.upper()}[/] "
                    f"{f.signal_type}  {loc}"
                )
                lines.append(f"    {f.description}")
        else:
            lines.append("[dim]No findings in this module.[/dim]")

        return "\n".join(lines)
