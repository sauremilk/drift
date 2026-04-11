"""drift start - guided onboarding path for first-time users."""

from __future__ import annotations

import click


@click.command("start", short_help="Guided first-run path in three commands.")
def start() -> None:
    """Show the recommended first-use journey: analyze -> fix-plan -> check."""
    click.echo(
        "Drift detects structural erosion from AI-assisted development — patterns your\n"
        "linter misses: duplicate helpers, layer boundary violations, fragmented error\n"
        "handling spreading across modules.\n"
    )
    click.echo("Here is the fastest path to your first findings:\n")

    click.echo("1) See what is structurally expensive right now")
    click.echo("   drift analyze --repo .")
    click.echo("")
    click.echo("2) Turn findings into concrete repair tasks")
    click.echo("   drift fix-plan --repo . --max-tasks 5")
    click.echo("")
    click.echo("3) Add a safe CI gate (report-only first)")
    click.echo("   drift check --fail-on none")
    click.echo("")
    click.echo("What to expect:")
    click.echo("  analyze   5-30 s scan, findings table with file references and next steps")
    click.echo("  fix-plan  5 actionable repair tasks, prioritized by estimated score delta")
    click.echo("  check     CI gate (0 exit code with --fail-on none until you're ready)")
    click.echo("")
    click.echo("Run 'drift explain <SIGNAL>' to understand any signal.")
    click.echo("Example: drift explain PFS")
    click.echo("")
    click.echo("When the team trusts the output, tighten the gate to:")
    click.echo("   drift check --fail-on high")
