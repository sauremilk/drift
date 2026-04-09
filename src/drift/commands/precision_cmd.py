"""``drift precision`` — Measure ground-truth precision/recall for signals."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import click

from drift.models import SignalType

# Common 3-letter abbreviations used in docs and CLI
_SIGNAL_ABBREVS: dict[str, str] = {
    "pfs": "pattern_fragmentation",
    "avs": "architecture_violation",
    "mds": "mutant_duplicate",
    "eds": "explainability_deficit",
    "dia": "doc_impl_drift",
    "tvs": "temporal_volatility",
    "sms": "system_misalignment",
    "bem": "broad_exception_monoculture",
    "tpd": "test_polarity_deficit",
    "gcd": "guard_clause_deficit",
    "cod": "cohesion_deficit",
    "nbv": "naming_contract_violation",
    "bat": "bypass_accumulation",
    "ecm": "exception_contract_drift",
    "ccc": "co_change_coupling",
    "tsa": "ts_architecture",
    "cxs": "cognitive_complexity",
    "foe": "fan_out_explosion",
    "cir": "circular_import",
    "dca": "dead_code_accumulation",
    "maz": "missing_authorization",
    "isd": "insecure_default",
    "hsc": "hardcoded_secret",
}


def _resolve_signal_type(name: str) -> SignalType | None:
    """Resolve a signal type from its value, name, or 3-letter abbreviation."""
    key = name.strip().lower()
    # Try abbreviation first
    if key in _SIGNAL_ABBREVS:
        return SignalType(_SIGNAL_ABBREVS[key])
    # Try enum value directly
    try:
        return SignalType(key)
    except ValueError:
        pass
    # Try enum name (e.g. TEMPORAL_VOLATILITY)
    try:
        return SignalType[key.upper()]
    except KeyError:
        return None

if TYPE_CHECKING:
    from drift.precision import PrecisionRecallReport


@click.command("precision")
@click.option(
    "--signal",
    "signal_name",
    default=None,
    help="Filter to a single signal type (e.g. PFS, TVS).",
)
@click.option(
    "--kind",
    "kind_name",
    default=None,
    type=click.Choice(["positive", "negative", "boundary", "confounder"], case_sensitive=False),
    help="Filter to a fixture kind.",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option(
    "--threshold",
    default=0.0,
    type=float,
    help="Minimum per-signal F1; exit 1 if any signal is below.",
)
def precision(
    signal_name: str | None,
    kind_name: str | None,
    json_output: bool,
    threshold: float,
) -> None:
    """Run ground-truth fixtures and report per-signal precision/recall/F1."""
    from tests.fixtures.ground_truth import ALL_FIXTURES, FixtureKind

    from drift.precision import (
        ensure_signals_registered,
        evaluate_fixtures,
    )

    ensure_signals_registered()

    # Build signal filter
    signal_filter: set[SignalType] | None = None
    if signal_name:
        sig = _resolve_signal_type(signal_name)
        if sig is None:
            click.echo(f"Unknown signal type: {signal_name}", err=True)
            sys.exit(2)
        signal_filter = {sig}

    # Build fixture filter
    fixtures = list(ALL_FIXTURES)
    if kind_name:
        kind_map = {k.name.lower(): k for k in FixtureKind}
        target_kind = kind_map.get(kind_name.lower())
        if target_kind is None:
            click.echo(f"Unknown kind: {kind_name}", err=True)
            sys.exit(2)
        fixtures = [f for f in fixtures if f.inferred_kind == target_kind]

    if not fixtures:
        click.echo("No fixtures match the given filters.", err=True)
        sys.exit(2)

    # Run evaluation
    with tempfile.TemporaryDirectory(prefix="drift_precision_") as tmp:
        tmp_path = Path(tmp)
        report, warnings = evaluate_fixtures(fixtures, tmp_path, signal_filter=signal_filter)

    # Output
    if json_output:
        click.echo(report.to_json())
    else:
        _print_rich_table(report)
        if warnings:
            click.echo("")
            for w in warnings:
                click.echo(f"  ⚠ [{w.signal_type}] {w.message}")

    # Threshold gate
    if threshold > 0.0:
        failed = []
        for sig in report.all_signals:
            f1 = report.f1(sig)
            if report.tp[sig] + report.fp[sig] + report.fn[sig] > 0 and f1 < threshold:
                failed.append((sig, f1))
        if failed:
            if not json_output:
                click.echo("")
                for sig, f1 in failed:
                    click.echo(
                        f"  ✗ {sig.value}: F1={f1:.2f} < threshold={threshold:.2f}"
                    )
            sys.exit(1)


def _print_rich_table(report: PrecisionRecallReport) -> None:
    """Render a Rich table of P/R/F1 per signal."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        click.echo(report.summary())
        return

    table = Table(title="Ground-Truth Precision / Recall")
    table.add_column("Signal", style="cyan")
    table.add_column("TP", justify="right")
    table.add_column("TN", justify="right")
    table.add_column("FP", justify="right", style="red")
    table.add_column("FN", justify="right", style="red")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("F1", justify="right", style="bold")

    for sig in report.all_signals:
        f1 = report.f1(sig)
        f1_style = "green" if f1 >= 0.80 else ("yellow" if f1 >= 0.50 else "red")
        table.add_row(
            sig.value,
            str(report.tp[sig]),
            str(report.tn[sig]),
            str(report.fp[sig]),
            str(report.fn[sig]),
            f"{report.precision(sig):.2f}",
            f"{report.recall(sig):.2f}",
            f"[{f1_style}]{f1:.2f}[/{f1_style}]",
        )

    console = Console()
    console.print(table)
    console.print(f"\n  Macro-Average F1: [bold]{report.aggregate_f1():.2f}[/bold]")
