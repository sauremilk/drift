"""drift diff — agent-native change-focused drift analysis."""

from __future__ import annotations

from pathlib import Path

import click

from drift.api import diff as api_diff
from drift.api import to_json


@click.command("diff")
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option("--diff-ref", default="HEAD~1", help="Git ref to diff against.")
@click.option(
    "--uncommitted",
    is_flag=True,
    default=False,
    help="Analyze current working-tree changes against HEAD.",
)
@click.option(
    "--staged-only",
    is_flag=True,
    default=False,
    help="Analyze only staged changes.",
)
@click.option(
    "--target-path",
    "--path",
    default=None,
    help="Restrict decision logic to a subdirectory while surfacing out-of-scope noise.",
)
@click.option(
    "--baseline",
    "baseline_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Optional baseline file for new/resolved comparison.",
)
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Offline diff: source analyze JSON snapshot.",
)
@click.option(
    "--to-file",
    "to_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Offline diff: target analyze JSON snapshot.",
)
@click.option("--max-findings", type=int, default=10, help="Maximum findings to return.")
@click.option(
    "--response-detail",
    type=click.Choice(["concise", "detailed"]),
    default="concise",
    help="Response detail level.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.option(
    "--signals",
    default=None,
    help="Comma-separated signal abbreviations to include (e.g. 'PFS,BEM').",
)
@click.option(
    "--exclude-signals",
    default=None,
    help="Comma-separated signal abbreviations to exclude (e.g. 'MDS,DIA').",
)
def diff(
    path: Path,
    diff_ref: str,
    uncommitted: bool,
    staged_only: bool,
    target_path: str | None,
    baseline_file: Path | None,
    from_file: Path | None,
    to_file: Path | None,
    max_findings: int,
    response_detail: str,
    output: Path | None,
    signals: str | None,
    exclude_signals: str | None,
) -> None:
    """Run agent-native diff analysis and emit structured JSON."""
    if uncommitted and staged_only:
        raise click.UsageError("Use either --uncommitted or --staged-only, not both.")
    if (from_file is None) ^ (to_file is None):
        raise click.UsageError("Use --from-file and --to-file together.")

    signal_list = (
        [s.strip() for s in signals.split(",") if s.strip()]
        if signals
        else None
    )
    exclude_list = (
        [s.strip() for s in exclude_signals.split(",") if s.strip()]
        if exclude_signals
        else None
    )

    result = api_diff(
        path,
        diff_ref=diff_ref,
        uncommitted=uncommitted,
        staged_only=staged_only,
        baseline_file=str(baseline_file) if baseline_file else None,
        from_file=str(from_file) if from_file else None,
        to_file=str(to_file) if to_file else None,
        target_path=target_path,
        max_findings=max_findings,
        response_detail=response_detail,
        signals=signal_list,
        exclude_signals=exclude_list,
    )
    text = to_json(result)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)

    # Offline mode follows issue #355 success criterion:
    # exit 1 when newly introduced HIGH/CRITICAL findings are present.
    if (
        from_file is not None
        and to_file is not None
        and int(result.get("new_high_or_critical", 0)) > 0
    ):
        raise click.exceptions.Exit(1)
