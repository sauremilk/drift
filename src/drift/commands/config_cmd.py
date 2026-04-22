"""CLI commands for configuration inspection and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from drift.commands import console
from drift.config import DriftConfig, build_config_json_schema
from drift.errors import DriftError
from drift.profiles import PROFILES


@click.group("config")
def config() -> None:
    """Inspect and validate drift configuration."""


def _compact_value(value: Any) -> str:
    """Return a short user-facing rendering for config values."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, list):
        if not value:
            return "[]"
        if len(value) <= 3:
            return ", ".join(str(item) for item in value)
        return f"{len(value)} items"
    if isinstance(value, dict):
        if not value:
            return "{}"
        keys = list(value.keys())
        preview = ", ".join(str(key) for key in keys[:3])
        if len(keys) > 3:
            preview += f", ... (+{len(keys) - 3} more)"
        return preview
    return str(value)


def _collect_non_default_values(current: Any, default: Any, prefix: str = "") -> list[str]:
    """Collect dotted paths whose values differ from DriftConfig defaults."""
    if isinstance(current, dict) and isinstance(default, dict):
        changes: list[str] = []
        for key in sorted(set(current) | set(default)):
            if key not in current:
                continue
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in default:
                changes.append(f"{child_prefix} = {_compact_value(current[key])}")
                continue
            changes.extend(_collect_non_default_values(current[key], default[key], child_prefix))
        return changes

    if current != default and prefix:
        return [f"{prefix} = {_compact_value(current)}"]
    return []


def _preview_patterns(patterns: list[str], *, limit: int = 4) -> str:
    """Render the first few include/exclude globs for quick inspection."""
    if not patterns:
        return "none"
    preview = ", ".join(patterns[:limit])
    if len(patterns) > limit:
        preview += f", ... (+{len(patterns) - limit} more)"
    return preview


def _infer_profile_name(cfg: DriftConfig) -> str | None:
    """Best-effort detection of the built-in profile that matches the config."""
    if cfg.extends:
        return cfg.extends

    current_weights = cfg.weights.as_dict()
    current_thresholds = cfg.thresholds.model_dump(mode="json")
    current_policies = cfg.policies.model_dump(mode="json", exclude_none=True)

    for name, profile in PROFILES.items():
        if cfg.fail_on != profile.fail_on or cfg.auto_calibrate != profile.auto_calibrate:
            continue
        if any(
            abs(float(current_weights.get(key, 0.0)) - float(value)) > 1e-9
            for key, value in profile.weights.items()
        ):
            continue
        if any(current_thresholds.get(key) != value for key, value in profile.thresholds.items()):
            continue
        if any(current_policies.get(key) != value for key, value in profile.policies.items()):
            continue
        return name
    return None


def _print_config_overview(repo_path: Path, cfg: DriftConfig, cfg_path: Path | None) -> None:
    """Show a newcomer-friendly summary before the full YAML dump."""
    default_data = DriftConfig().model_dump(mode="json")
    current_data = cfg.model_dump(mode="json")
    non_defaults = _collect_non_default_values(current_data, default_data)
    inferred_profile = _infer_profile_name(cfg) or "custom/defaults"
    source_label = str(cfg_path) if cfg_path and cfg_path.exists() else "built-in defaults"

    console.print("[bold]Configuration overview[/bold]")
    console.print(f"  Source: {source_label}")
    console.print(f"  Active profile: {inferred_profile}")
    console.print(f"  Fail on: {cfg.fail_on}")
    console.print(f"  Auto-calibration: {'enabled' if cfg.auto_calibrate else 'disabled'}")
    console.print(f"  Include globs ({len(cfg.include)}): {_preview_patterns(cfg.include)}")
    console.print(f"  Exclude globs ({len(cfg.exclude)}): {_preview_patterns(cfg.exclude)}")

    if non_defaults:
        console.print("  Non-default values:")
        for item in non_defaults[:8]:
            console.print(f"    - {item}")
        if len(non_defaults) > 8:
            console.print(f"    - ... (+{len(non_defaults) - 8} more)")
    else:
        console.print("  Non-default values: none — using shipped defaults.")

    if not cfg.attribution.enabled:
        console.print(
            "  [dim]Attribution (git-blame provenance): disabled — "
            "enable with attribution.enabled: true in drift.yaml[/dim]"
        )

    recommended = "drift analyze --repo ."
    if cfg_path is None or not cfg_path.exists():
        console.print("  Recommended next: drift init --interactive")
        console.print(f"                    then {recommended}")
    else:
        console.print(f"  Recommended next: {recommended}")
    console.print()


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
        # Convert Pydantic validation errors into actionable field-level messages
        if isinstance(exc, ValidationError):
            messages = []
            for err in exc.errors():
                loc = " → ".join(str(p) for p in err.get("loc", ()))
                msg = err.get("msg", str(err))
                messages.append(f"  Field '{loc}': {msg}")
            detail = "\n".join(messages)
            console.print(
                f"[red]✗ Configuration invalid[/red] (DRIFT-1001):\n{detail}\n"
                "[dim]Run [bold]drift config validate[/bold] to re-check after editing.[/dim]"
            )
        else:
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
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Skip the onboarding summary and print only YAML.",
)
def show(repo: str, config_path: str | None, raw: bool) -> None:
    """Show the effective configuration after merging with defaults."""
    repo_path = Path(repo).resolve()
    cfg_path = Path(config_path) if config_path else None

    if cfg_path is None:
        cfg_path = DriftConfig._find_config_file(repo_path)

    try:
        cfg = DriftConfig.load(repo_path, cfg_path)
    except DriftError as exc:
        console.print(f"[red]Error loading config:[/red] {exc.detail}")
        raise SystemExit(1) from None
    except (ValueError, ValidationError) as exc:
        console.print(f"[red]Error loading config:[/red] {exc}")
        raise SystemExit(1) from None

    import yaml  # type: ignore[import-untyped]

    if not raw:
        _print_config_overview(repo_path, cfg, cfg_path)

    data = cfg.model_dump(mode="json")
    console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))


@config.command()
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(),
    help="Write schema JSON to a file instead of stdout.",
)
def schema(output_path: str | None) -> None:
    """Print the JSON Schema for drift.yaml configuration files."""
    schema_data = build_config_json_schema()
    rendered = json.dumps(schema_data, indent=2, sort_keys=True)

    if output_path:
        target = Path(output_path)
        target.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Wrote config schema to [bold]{target}[/bold]")
        return

    click.echo(rendered)
