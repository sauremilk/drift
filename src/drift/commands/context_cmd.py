"""drift context — generate pre-edit guard contracts for AI agents."""

from __future__ import annotations

import json
from pathlib import Path

import click

from drift.commands import console
from drift.commands._io import _emit_machine_output


@click.command("context")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--target",
    "-t",
    required=True,
    help="File or module path to generate the contract for (relative to repo root).",
)
@click.option(
    "--for-agent",
    is_flag=True,
    default=False,
    help="Output a machine-readable guard contract (JSON) for AI agents.",
)
@click.option(
    "--include-findings",
    is_flag=True,
    default=False,
    help="Include existing drift findings for the target in the contract.",
)
@click.option(
    "--max-findings",
    type=int,
    default=10,
    help="Maximum findings to include (only with --include-findings).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "rich"]),
    default="json",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout).",
)
def context(
    repo: Path,
    target: str,
    for_agent: bool,
    include_findings: bool,
    max_findings: int,
    output_format: str,
    output: Path | None,
) -> None:
    """Generate a pre-edit guard contract for a file or module.

    The contract tells AI agents which architectural constraints,
    invariants, and boundaries apply before editing a target.

    \b
    Examples:
      drift context --for-agent --target src/drift/signals/pfs.py
      drift context -t src/drift/api/ --include-findings --format rich
    """
    from drift.api.guard_contract import guard_contract

    result = guard_contract(
        path=str(repo.resolve()),
        target=target,
        include_findings=include_findings,
        max_findings=max_findings,
    )

    if result.get("status") != "ok":
        console.print(f"[red]Error:[/red] {result.get('message', 'Unknown error')}")
        raise SystemExit(1)

    if output_format == "json" or for_agent:
        payload = json.dumps(result, indent=2, default=str)
        _emit_machine_output(payload, output)
        return

    # Rich output
    _render_rich(result)


def _render_rich(result: dict) -> None:  # type: ignore[type-arg]
    """Render guard contract as a readable Rich table."""
    from rich.panel import Panel
    from rich.table import Table

    target = result.get("target", "?")
    boundary = result.get("boundary_contract", {})
    guard = result.get("pre_edit_guard", {})

    # Header
    console.print(
        Panel(
            f"[bold]Guard Contract[/bold] for [cyan]{target}[/cyan]\n"
            f"Layer: [yellow]{boundary.get('layer', '?')}[/yellow]  ·  "
            f"Module: {result.get('module', '?')}",
            title="drift context",
        )
    )

    # Boundary table
    bt = Table(title="Boundary Contract", show_header=True)
    bt.add_column("Property", style="bold")
    bt.add_column("Value")

    bt.add_row("Allowed imports", ", ".join(boundary.get("allowed_imports_from", [])) or "—")
    bt.add_row(
        "Forbidden imports",
        ", ".join(boundary.get("forbidden_imports_from", [])) or "—",
    )
    bt.add_row("Public API", ", ".join(boundary.get("public_api_surface", [])[:10]) or "—")
    bt.add_row("Neighbors", ", ".join(boundary.get("neighbors", [])[:8]) or "—")

    decisions = boundary.get("arch_decisions", [])
    if decisions:
        for d in decisions[:5]:
            bt.add_row(f"Rule ({d.get('id', '?')})", d.get("constraint", ""))

    console.print(bt)

    # Guard table
    gt = Table(title="Pre-Edit Guard", show_header=True)
    gt.add_column("Property", style="bold")
    gt.add_column("Value")

    gt.add_row("Dependencies", ", ".join(guard.get("dependencies", [])) or "—")
    gt.add_row("Related tests", ", ".join(guard.get("related_tests", [])) or "—")
    gt.add_row("Active signals", ", ".join(guard.get("active_signals_affecting", [])) or "—")

    findings = guard.get("known_findings", [])
    gt.add_row("Known findings", str(len(findings)))

    for inv in guard.get("invariants", []):
        gt.add_row("Invariant", inv)

    console.print(gt)

    # Agent instruction
    instruction = result.get("agent_instruction", "")
    if instruction:
        console.print(Panel(instruction, title="Agent Instruction", border_style="green"))
