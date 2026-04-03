"""drift brief — pre-task structural briefing for agent delegation."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from drift.api import brief as api_brief
from drift.api import to_json
from drift.commands._io import _write_output_file
from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD


def _render_risk_bar(level: str) -> str:
    """Return a compact visual risk indicator."""
    bars = {"LOW": "■□□□", "MEDIUM": "■■□□", "HIGH": "■■■□", "BLOCK": "■■■■"}
    return bars.get(level, "????")


@click.command("brief")
@click.option(
    "--task",
    "-t",
    required=True,
    help="Natural-language task description.",
)
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option(
    "--scope",
    "scope_override",
    default=None,
    help="Manual scope override (path or glob, e.g. src/checkout/).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "markdown"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write output to a file instead of stdout.",
)
@click.option(
    "--max-guardrails",
    type=click.IntRange(min=1, max=50),
    default=10,
    help="Maximum number of guardrails to generate (1-50).",
)
@click.option(
    "--select",
    "--signals",
    "select_signals",
    default=None,
    help="Comma-separated signal IDs to evaluate (e.g. PFS,AVS,MDS).",
)
@click.option(
    "--include-non-operational",
    is_flag=True,
    default=False,
    help="Include fixture/generated/migration/docs findings.",
)
@click.option(
    "--json",
    "json_shortcut",
    is_flag=True,
    default=False,
    help="Shortcut for --format json.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Only print guardrails (no briefing header).",
)
def brief(
    task: str,
    path: Path,
    scope_override: str | None,
    output_format: str,
    output: Path | None,
    max_guardrails: int,
    select_signals: str | None,
    include_non_operational: bool,
    json_shortcut: bool,
    quiet: bool,
) -> None:
    """Generate a pre-task structural briefing before agent delegation.

    Analyses the repository scope affected by a task description and produces
    guardrails (prompt constraints) that reduce architectural erosion risk
    during AI-assisted code generation.

    \b
    Examples:
        drift brief --task "add payment integration to checkout module"
        drift brief -t "refactor auth service" --format json
        drift brief -t "add caching to API layer" --scope src/api/ --json
    """
    if json_shortcut:
        output_format = "json"

    # Redirect console output when using machine-readable formats
    if output_format != "rich":
        from rich.console import Console

        import drift.commands as _cmds

        _cmds.console = Console(stderr=True)

    signals = (
        [s.strip() for s in select_signals.split(",") if s.strip()]
        if select_signals
        else None
    )

    result = api_brief(
        path,
        task=task,
        scope_override=scope_override,
        signals=signals,
        max_guardrails=max_guardrails,
        include_non_operational=include_non_operational,
    )

    if output_format == "json":
        text = to_json(result)
        if output is not None:
            _write_output_file(text, output)
            click.echo(f"Output written to {output}", err=True)
        else:
            click.echo(text)

    elif output_format == "markdown":
        text = _format_markdown(result)
        if output is not None:
            _write_output_file(text, output)
            click.echo(f"Output written to {output}", err=True)
        else:
            click.echo(text)

    else:
        _render_rich(result, quiet=quiet)

    # Exit 1 for BLOCK risk level
    if result.get("risk", {}).get("level") == "BLOCK":
        sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)


# ---------------------------------------------------------------------------
# Rich output
# ---------------------------------------------------------------------------


def _render_rich(result: dict, *, quiet: bool = False) -> None:
    """Render the brief result as a rich terminal table."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    risk = result.get("risk", {})
    scope = result.get("scope", {})
    landscape = result.get("landscape", {})
    guardrails = result.get("guardrails", [])

    if not quiet:
        # Header panel
        level = risk.get("level", "?")
        bar = _render_risk_bar(level)
        paths_str = ", ".join(scope.get("resolved_paths", [])) or "(entire repository)"
        conf = scope.get("confidence", 0)
        conf_note = f" (confidence: {conf:.0%})" if conf < 0.8 else ""

        header_lines = [
            f"[bold]Task:[/bold] {result.get('task', '?')}",
            f"[bold]Scope:[/bold] {paths_str}{conf_note}",
            f"[bold]Risk:[/bold] {bar} {level}",
        ]
        reason = risk.get("reason", "")
        if reason:
            header_lines.append(f"[bold]Reason:[/bold] {reason}")

        console.print(Panel(
            "\n".join(header_lines),
            title="[bold blue]Drift Brief[/bold blue]",
            border_style="blue",
        ))

        # Signal landscape table
        top_signals = landscape.get("top_signals", [])
        if top_signals:
            table = Table(title="Structural Landscape", show_header=True)
            table.add_column("Signal", style="bold")
            table.add_column("Score", justify="right")
            table.add_column("Findings", justify="right")
            for sig in top_signals[:8]:
                score = sig.get("score", 0)
                filled = int(score * 10)
                bar_vis = "■" * filled + "░" * (10 - filled)
                table.add_row(
                    sig.get("signal", "?"),
                    f"{bar_vis} {score:.2f}",
                    str(sig.get("finding_count", 0)),
                )
            console.print(table)
            console.print()

    # Guardrails panel
    if guardrails:
        lines = []
        for i, gr in enumerate(guardrails, start=1):
            sig = gr.get("signal", "?")
            constraint = gr.get("constraint", "")
            forbidden = gr.get("forbidden", "")
            reason = gr.get("reason", "")

            lines.append(f"[bold]{i}. [{sig}][/bold] {constraint}")
            if forbidden:
                # Strip code-block prefix for display
                short_forbidden = forbidden.replace("# ANTI-PATTERN:", "").strip()
                if short_forbidden:
                    lines.append(f"   [dim]— do NOT: {short_forbidden}[/dim]")
            if reason:
                lines.append(f"   [italic]Reason: {reason}[/italic]")
            lines.append("")

        console.print(Panel(
            "\n".join(lines).rstrip(),
            title="[bold green]Guardrails (copy to agent prompt)[/bold green]",
            border_style="green",
        ))
    elif not quiet:
        console.print("[green]✓ Scope is structurally healthy — no guardrails needed.[/green]")

    if not quiet:
        console.print(
            "\n[dim]Suggested follow-up: drift diff --uncommitted after implementation[/dim]"
        )


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------


def _format_markdown(result: dict) -> str:
    """Format result as agent-context-optimised markdown."""
    risk = result.get("risk", {})
    scope = result.get("scope", {})
    guardrails = result.get("guardrails", [])
    landscape = result.get("landscape", {})

    paths_str = ", ".join(scope.get("resolved_paths", [])) or "(entire repository)"
    level = risk.get("level", "?")

    lines = [
        "## Structural Constraints (generated by drift brief)",
        "",
        f"**Task:** {result.get('task', '?')}",
        f"**Scope:** {paths_str} | **Risk:** {level} ({risk.get('score', 0):.2f})",
        "",
    ]

    if guardrails:
        lines.append("### Guardrails")
        lines.append("")
        for i, gr in enumerate(guardrails, start=1):
            sig = gr.get("signal", "?")
            constraint = gr.get("constraint", "")
            lines.append(f"{i}. **[{sig}]** {constraint}")
        lines.append("")

    top_signals = landscape.get("top_signals", [])
    if top_signals:
        lines.append("### Landscape")
        sig_parts = [
            f"{s.get('signal', '?')}: {s.get('score', 0):.2f}"
            f" ({s.get('finding_count', 0)} findings)"
            for s in top_signals[:6]
        ]
        lines.append("- " + " | ".join(sig_parts))
        lines.append("")

    return "\n".join(lines)
