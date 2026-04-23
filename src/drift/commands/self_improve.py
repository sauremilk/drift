"""``drift self-improve`` — run one Self-Improvement Loop cycle (ADR-097/098)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click

from drift.self_improvement import close_proposal, run_cycle
from drift.self_improvement.engine import DEFAULT_CLOSED_LOG, ImprovementReport


@click.group(name="self-improve", hidden=True)
def self_improve() -> None:
    """Drift Self-Improvement Loop (DSOL).

    Runs a single bounded analysis cycle on the drift repo itself
    and emits human-reviewable proposals — never an automatic patch.
    Designed to be invoked weekly from a cron workflow so optimization
    pressure compounds over time without requiring agent autonomy.
    """


@self_improve.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root.",
)
@click.option(
    "--max-proposals",
    type=int,
    default=10,
    show_default=True,
    help="Hard cap on proposals per cycle (flood guard).",
)
@click.option(
    "--trend-window",
    type=int,
    default=5,
    show_default=True,
    help="KPI snapshots to consider for slope detection.",
)
@click.option(
    "--min-score",
    "min_proposal_score",
    type=float,
    default=0.0,
    show_default=True,
    help="Minimum proposal score — proposals below this threshold are dropped.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
)
def run(
    repo: Path,
    max_proposals: int,
    trend_window: int,
    min_proposal_score: float,
    output_format: str,
) -> None:
    """Run one DSOL cycle and print a brief summary."""
    report = run_cycle(
        repo=repo,
        max_proposals=max_proposals,
        trend_window=trend_window,
        min_proposal_score=min_proposal_score,
    )

    if output_format == "json":
        click.echo(report.model_dump_json(indent=2))
        return

    click.echo(f"Self-Improvement cycle: {report.cycle_ts}")
    click.echo(f"Proposals: {len(report.proposals)}")
    for obs in report.observations:
        click.echo(f"  ! {obs}")
    for p in report.proposals:
        marker = "*" if p.recurrence > 1 else "-"
        click.echo(f"  {marker} [{p.kind}] {p.proposal_id} (score={p.score})")
    click.echo(
        f"Artifacts: work_artifacts/self_improvement/{report.cycle_ts}/ "
        f"(proposals.json, summary.md)"
    )


@self_improve.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root.",
)
def ledger(repo: Path) -> None:
    """Show the recurrence ledger of past cycles (read-only)."""
    ledger_path = Path(repo) / ".drift" / "self_improvement_ledger.jsonl"
    if not ledger_path.exists():
        click.echo("no ledger yet — run `drift self-improve run` first.")
        return
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows[-20:]:
        ids = row.get("proposal_ids") or []
        click.echo(f"{row.get('cycle_ts')}  ({len(ids)} proposals)")


# ---------------------------------------------------------------------------
# apply — write action-artefacts from a proposals.json (ADR-098)
# ---------------------------------------------------------------------------

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _safe_stem(text: str, maxlen: int = 40) -> str:
    """Convert arbitrary text to a safe filename stem."""
    return _SAFE_ID_RE.sub("_", text)[:maxlen].strip("_") or "unknown"


def _write_action(output_dir: Path, filename: str, content: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


@self_improve.command()
@click.option(
    "--proposals",
    "proposals_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to proposals.json from a previous DSOL cycle.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print planned actions without writing any files.",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for action artefacts (default: <proposals_dir>/../../dsol_actions).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
)
def apply(
    proposals_path: Path,
    dry_run: bool,
    output_dir: Path | None,
    output_format: str,
) -> None:
    """Write action-artefacts for each proposal (ADR-098 write-back).

    Produces human-reviewable Markdown files (ADR stubs, triage guides,
    audit action notes) — never modifies source code or scoring config.
    """
    raw = json.loads(proposals_path.read_text(encoding="utf-8"))
    report = ImprovementReport.model_validate(raw)

    if output_dir is None:
        # Default: work_artifacts/dsol_actions/<cycle_ts>/
        output_dir = proposals_path.parent.parent.parent / "dsol_actions" / report.cycle_ts

    created: list[str] = []

    for p in report.proposals:
        kind = p.kind
        if kind == "stale_audit":
            filename = f"stale_audit_action_{_safe_stem(report.cycle_ts)}.md"
            content = (
                f"# Stale Audit Action — {report.cycle_ts}\n\n"
                f"**Proposal:** `{p.proposal_id}`\n\n"
                f"**Rationale:** {p.rationale}\n\n"
                f"## Required Action\n\n"
                f"{p.suggested_action}\n\n"
                f"```sh\nmake audit-diff\n```\n"
            )
        elif kind == "regressive_signal":
            stem = _safe_stem(p.signal_type or p.proposal_id)
            filename = f"adr_stub_{stem}.md"
            content = (
                f"# ADR Draft — Regressive Signal: {p.signal_type or p.proposal_id}\n\n"
                f"- Status: proposed\n"
                f"- Generated by DSOL cycle: {report.cycle_ts}\n\n"
                f"## Context\n\n{p.rationale}\n\n"
                f"## Suggested Action\n\n{p.suggested_action}\n\n"
                f"## Decision\n\n_[Maintainer fills in]_\n\n"
                f"## Consequences\n\n_[Maintainer fills in]_\n"
            )
        elif kind == "fp_rate_exceeded":
            stem = _safe_stem(p.signal_type or p.proposal_id)
            filename = f"fp_triage_{stem}.md"
            content = (
                f"# FP Triage — {p.signal_type or p.proposal_id}\n\n"
                f"**Generated by DSOL cycle:** {report.cycle_ts}\n\n"
                f"## Finding\n\n{p.rationale}\n\n"
                f"## Triage Steps\n\n{p.suggested_action}\n\n"
                f"1. Open `benchmark_results/oracle_fp_report.json`\n"
                f"2. Review labeled samples for signal `{p.signal_type}`\n"
                f"3. Classify root cause (threshold / scope / semantic)\n"
                f"4. Decide: adjust threshold, add suppression, or file ADR\n"
            )
        elif kind == "hotspot_finding":
            stem = _safe_stem(p.proposal_id)
            filename = f"hotspot_{stem}.md"
            content = (
                f"# Hotspot Finding Action — {report.cycle_ts}\n\n"
                f"**Proposal:** `{p.proposal_id}`\n"
                f"**Signal:** `{p.signal_type}`\n"
                f"**File:** `{p.file_path}`\n"
                f"**Severity:** `{p.severity}`\n\n"
                f"## Rationale\n\n{p.rationale}\n\n"
                f"## Suggested Action\n\n{p.suggested_action}\n"
            )
        else:
            stem = _safe_stem(p.proposal_id)
            filename = f"action_{stem}.md"
            content = (
                f"# Action — {p.proposal_id}\n\n"
                f"**Cycle:** {report.cycle_ts}\n\n"
                f"## Rationale\n\n{p.rationale}\n\n"
                f"## Suggested Action\n\n{p.suggested_action}\n"
            )

        if dry_run:
            click.echo(f"[dry-run] would write: {output_dir / filename}")
        else:
            path = _write_action(output_dir, filename, content)
            created.append(str(path))

    if output_format == "json":
        click.echo(json.dumps({"dry_run": dry_run, "created": created}))
    else:
        if dry_run:
            click.echo(f"Dry-run complete. {len(report.proposals)} action(s) planned.")
        else:
            click.echo(f"Applied {len(created)} action artefact(s) to {output_dir}")


@self_improve.command()
@click.argument("proposal_id")
@click.option(
    "--note",
    "outcome_note",
    default="",
    help="Short outcome note (e.g. 'implemented in PR #42').",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root (determines closed-log path).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def close(
    proposal_id: str,
    outcome_note: str,
    repo: Path,
    output_format: str,
) -> None:
    """Mark PROPOSAL_ID as closed in the closed-proposals log.

    Closed proposals are subtracted from the recurrence-tracking set
    so they no longer accumulate priority pressure in future cycles.

    Example::

        drift self-improve close DSOL-abc123 --note "fixed in PR #42"
    """
    closed_path = repo / DEFAULT_CLOSED_LOG
    entry = close_proposal(proposal_id, outcome_note, closed_path=closed_path)
    if output_format == "json":
        click.echo(entry.model_dump_json())
    else:
        click.echo(f"Closed {entry.proposal_id} at {entry.closed_at}")
