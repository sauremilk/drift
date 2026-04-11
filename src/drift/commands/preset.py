"""drift preset — discover and list available configuration presets."""

from __future__ import annotations

import click

from drift.commands import console


@click.group("preset", short_help="Manage configuration presets.")
def preset() -> None:
    """Discover, list, and inspect configuration presets.

    Presets provide pre-tuned signal weights, thresholds, and policies
    for common project types. Use ``extends: <preset>`` in drift.yaml
    to inherit a preset's configuration.
    """


@preset.command("list")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def preset_list(output_json: bool) -> None:
    """List all available presets (built-in and plugin-provided)."""
    import json as json_mod

    from rich.table import Table

    from drift.profiles import list_profiles

    # Discover external presets via entry points
    external = _discover_external_presets()

    if output_json:
        items = []
        for p in list_profiles():
            items.append(
                {
                    "name": p.name,
                    "description": p.description,
                    "source": "built-in",
                    "fail_on": p.fail_on,
                    "auto_calibrate": p.auto_calibrate,
                    "signals": len(p.weights),
                }
            )
        for name, desc in external:
            items.append(
                {
                    "name": name,
                    "description": desc,
                    "source": "plugin",
                }
            )
        console.print_json(json_mod.dumps(items, indent=2))
        return

    table = Table(title="Available Presets", show_header=True)
    table.add_column("Name", min_width=15, style="bold")
    table.add_column("Source", min_width=10)
    table.add_column("Fail On", min_width=8)
    table.add_column("Signals", justify="right", min_width=8)
    table.add_column("Description", max_width=60)

    for p in list_profiles():
        table.add_row(
            p.name,
            "[dim]built-in[/dim]",
            p.fail_on,
            str(len(p.weights)),
            p.description[:60],
        )

    for name, desc in external:
        table.add_row(
            name,
            "[cyan]plugin[/cyan]",
            "—",
            "—",
            desc[:60] if desc else "—",
        )

    console.print(table)

    console.print()
    console.print("[dim]Use a preset in drift.yaml:[/dim]  [bold]extends: <name>[/bold]")


@preset.command("show")
@click.argument("name")
def preset_show(name: str) -> None:
    """Show details for a specific preset."""
    import json as json_mod

    from drift.profiles import get_profile

    try:
        p = get_profile(name)
    except KeyError as exc:
        console.print(f"[red]Unknown preset: {name}[/red]")
        raise SystemExit(1) from exc

    console.print(f"[bold]{p.name}[/bold] — {p.description}")
    console.print()
    console.print(f"  [bold]fail_on:[/bold] {p.fail_on}")
    console.print(f"  [bold]auto_calibrate:[/bold] {p.auto_calibrate}")
    console.print()

    console.print("[bold]Signal Weights:[/bold]")
    for sig, weight in sorted(p.weights.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(weight * 50) + "░" * (10 - int(weight * 50))
        console.print(f"  {bar} {weight:.3f}  {sig}")

    if p.thresholds:
        console.print()
        console.print("[bold]Thresholds:[/bold]")
        for key, val in sorted(p.thresholds.items()):
            console.print(f"  {key}: {val}")

    if p.policies:
        console.print()
        console.print("[bold]Policies:[/bold]")
        console.print_json(json_mod.dumps(p.policies, indent=2))


def _discover_external_presets() -> list[tuple[str, str]]:
    """Discover presets registered via entry points."""
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="drift.presets")
        results = []
        for ep in eps:
            try:
                obj = ep.load()
                desc = getattr(obj, "description", "") if obj else ""
                results.append((ep.name, desc))
            except Exception:  # noqa: BLE001
                results.append((ep.name, "(failed to load)"))
        return results
    except Exception:  # noqa: BLE001
        return []
