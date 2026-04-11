"""drift start - guided onboarding path for first-time users."""

from __future__ import annotations

import click


@click.command("start", short_help="Guided first-run path in three commands.")
def start() -> None:
    """Show the recommended first-use journey: analyze -> fix-plan -> check."""
    click.echo("Drift start: the fastest path to useful results")
    click.echo("")
    click.echo("1) See what is structurally expensive right now")
    click.echo("   drift analyze --repo .")
    click.echo("")
    click.echo("2) Turn findings into concrete repair tasks")
    click.echo("   drift fix-plan --repo . --max-tasks 5")
    click.echo("")
    click.echo("3) Add a safe CI gate (report-only first)")
    click.echo("   drift check --fail-on none")
    click.echo("")
    click.echo("When the team trusts the output, tighten the gate to:")
    click.echo("   drift check --fail-on high")
