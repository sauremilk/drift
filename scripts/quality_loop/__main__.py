"""CLI entry point: python -m scripts.quality_loop"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from scripts.quality_loop.evaluate import evaluate_cmd
from scripts.quality_loop.orchestrator import HybridOrchestrator


@click.group()
def cli() -> None:
    """Quality loop: autonomous code quality improvement via MCTS + GA."""


cli.add_command(evaluate_cmd)


@cli.command()
@click.option(
    "--src",
    default="src/drift",
    show_default=True,
    help="Source root to analyse and transform (relative to cwd).",
)
@click.option(
    "--mode",
    type=click.Choice(["mcts", "genetic", "hybrid"]),
    default="hybrid",
    show_default=True,
    help="Search mode: mcts-only, genetic-only, or hybrid (MCTS seeds GA).",
)
@click.option(
    "--mcts-budget",
    default=50,
    show_default=True,
    help="Number of MCTS iterations.",
)
@click.option(
    "--ga-generations",
    default=20,
    show_default=True,
    help="Number of GA generations.",
)
@click.option(
    "--ga-population",
    default=10,
    show_default=True,
    help="GA population size.",
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help="Random seed for reproducibility.",
)
@click.option(
    "--output-json",
    default=None,
    help="Path to write the JSON result (default: print to stdout).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Analyse and plan but do not write any changes to disk.",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit 0, even when no improvement was found.",
)
@click.option(
    "--min-improvement",
    default=0.01,
    show_default=True,
    help="Minimum composite score improvement required to apply changes.",
)
def run(
    src: str,
    mode: str,
    mcts_budget: int,
    ga_generations: int,
    ga_population: int,
    seed: int | None,
    output_json: str | None,
    dry_run: bool,
    exit_zero: bool,
    min_improvement: float,
) -> None:
    """Run the quality improvement loop against a source directory."""
    src_root = Path(src).resolve()
    if not src_root.exists():
        click.echo(f"Error: source root does not exist: {src_root}", err=True)
        sys.exit(1)

    click.echo(f"[quality-loop] mode={mode} src={src_root} dry_run={dry_run}")

    orchestrator = HybridOrchestrator(
        src_root=src_root,
        mode=mode,
        budget_mcts=mcts_budget,
        budget_ga_gen=ga_generations,
        budget_ga_pop=ga_population,
        min_improvement=min_improvement,
        dry_run=dry_run,
        seed=seed,
    )

    result = orchestrator.run()
    result_dict = result.to_dict()

    # Output
    if output_json:
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result_dict, indent=2), encoding="utf-8")
        click.echo(f"[quality-loop] Result written to {out_path}")
    else:
        click.echo(json.dumps(result_dict, indent=2))

    # Summary line
    status = "APPLIED" if result.applied else ("DRY-RUN" if dry_run else "NO CHANGE")
    click.echo(
        f"[quality-loop] baseline={result.baseline_score:.4f} "
        f"final={result.final_score:.4f} "
        f"improvement={result.improvement:+.4f} "
        f"status={status}"
    )

    if not exit_zero and result.improvement < min_improvement and not dry_run:
        sys.exit(1)


if __name__ == "__main__":
    cli()
