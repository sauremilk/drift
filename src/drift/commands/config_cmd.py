"""CLI commands for configuration inspection and validation."""

from __future__ import annotations

from pathlib import Path

import click
from pydantic import ValidationError

from drift.commands import console
from drift.config import DriftConfig
from drift.errors import DriftError


@click.group("config")
def config() -> None:
    """Inspect and validate drift configuration."""


@config.command()
@click.option("--repo", default=".", type=click.Path(exists=True), help="Repository root.")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path.")
def validate(repo: str, config_path: str | None) -> None:
    """Validate a drift.yaml configuration file."""
    repo_path = Path(repo).resolve()
    cfg_path = Path(config_path) if config_path else None

    # Resolve config file location for display
    if cfg_path is None:
        cfg_path = DriftConfig._find_config_file(repo_path)

    if cfg_path is None or not cfg_path.exists():
        console.print("[yellow]No drift config file found — defaults will be used.[/yellow]")
        console.print("[green]✓[/green] Default configuration is valid.")
        return

    console.print(f"Validating [bold]{cfg_path}[/bold] …")

    try:
        cfg = DriftConfig.load(repo_path, cfg_path)
    except DriftError as exc:
        console.print(f"[red]✗ Configuration invalid:[/red]\n{exc.detail}")
        raise SystemExit(1) from None
    except (ValueError, ValidationError) as exc:
        console.print(f"[red]✗ Configuration invalid:[/red]\n{exc}")
        raise SystemExit(1) from None

    # Business-rule checks
    warnings: list[str] = []

    weight_sum = sum(cfg.weights.as_dict().values())
    if weight_sum < 0.5 or weight_sum > 2.0:
        warnings.append(
            f"Signal weights sum to {weight_sum:.3f} — expected roughly 1.0. "
            "Auto-calibration normalises at runtime, but extreme values may distort scores."
        )

    for key, val in cfg.weights.as_dict().items():
        if val < 0:
            warnings.append(f"Weight '{key}' is negative ({val}) — this is not supported.")

    if cfg.thresholds.similarity_threshold < 0 or cfg.thresholds.similarity_threshold > 1:
        warnings.append(
            f"similarity_threshold={cfg.thresholds.similarity_threshold} outside [0, 1]."
        )

    # Validate path_overrides glob patterns
    for pattern, override in cfg.path_overrides.items():
        for sig_name in override.exclude_signals:
            from drift.models import SignalType

            valid_signals = {s.value for s in SignalType}
            if sig_name not in valid_signals:
                warnings.append(
                    f"path_overrides['{pattern}'].exclude_signals: "
                    f"unknown signal '{sig_name}'."
                )

    if warnings:
        console.print(f"[yellow]⚠ {len(warnings)} warning(s):[/yellow]")
        for w in warnings:
            console.print(f"  • {w}")
    else:
        console.print("[green]✓[/green] Configuration is valid — no warnings.")


@config.command()
@click.option("--repo", default=".", type=click.Path(exists=True), help="Repository root.")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path.")
def show(repo: str, config_path: str | None) -> None:
    """Show the effective configuration after merging with defaults."""
    repo_path = Path(repo).resolve()
    cfg_path = Path(config_path) if config_path else None

    try:
        cfg = DriftConfig.load(repo_path, cfg_path)
    except DriftError as exc:
        console.print(f"[red]Error loading config:[/red] {exc.detail}")
        raise SystemExit(1) from None
    except (ValueError, ValidationError) as exc:
        console.print(f"[red]Error loading config:[/red] {exc}")
        raise SystemExit(1) from None

    import yaml  # type: ignore[import-untyped]

    data = cfg.model_dump(mode="json")
    console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))
