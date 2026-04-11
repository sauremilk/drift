"""drift completions — generate shell completion scripts."""

from __future__ import annotations

import click

_SHELLS = ("bash", "zsh", "fish")

_SHELL_MAP = {
    "bash": "bash",
    "zsh": "zsh",
    "fish": "fish",
}


@click.command()
@click.argument("shell", type=click.Choice(_SHELLS))
def completions(shell: str) -> None:
    """Generate shell completion script for drift.

    Supported shells: bash, zsh, fish, powershell.

    \b
    Examples:
        drift completions bash > ~/.drift-completion.bash
        source ~/.drift-completion.bash

        drift completions zsh > ~/.zfunc/_drift
        drift completions fish > ~/.config/fish/completions/drift.fish
    """
    from click.shell_completion import get_completion_class

    from drift.cli import main

    cls = get_completion_class(_SHELL_MAP[shell])
    if cls is None:
        raise click.ClickException(f"Unsupported shell: {shell}")
    comp = cls(main, {}, "drift", "_DRIFT_COMPLETE")
    # Use the template directly to avoid _check_version() calling the
    # shell binary (fails on Windows when bash is not installed).
    script = comp.source_template % {
        "complete_func": comp.func_name,
        "complete_var": comp.complete_var,
        "prog_name": comp.prog_name,
    }
    click.echo(script)
