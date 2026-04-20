"""Interactive per-finding feedback triage for ``drift analyze --review``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console

    from drift.models import Finding

# Number of accumulated feedback entries that triggers the calibration hint.
_CALIBRATION_HINT_THRESHOLD: int = 10

_SIGNAL_ABBREVS: dict[str, str] = {
    "pattern_fragmentation": "PFS",
    "architecture_violation": "AVS",
    "mutant_duplicate": "MDS",
    "explainability_deficit": "EDS",
    "doc_impl_drift": "DIA",
    "temporal_volatility": "TVS",
    "system_misalignment": "SMS",
    "broad_exception_monoculture": "BEM",
    "test_polarity_deficit": "TPD",
    "guard_clause_deficit": "GCD",
    "naming_contract_violation": "NBV",
    "bypass_accumulation": "BAT",
    "exception_contract_drift": "ECM",
    "co_change_coupling": "CCC",
    "ts_architecture": "TSA",
    "cohesion_deficit": "COD",
    "missing_authorization": "MAZ",
    "insecure_default": "ISD",
    "hardcoded_secret": "HSC",  # pragma: allowlist secret
    "phantom_reference": "PHR",
    "type_safety_bypass": "TSB",
    "fan_out_explosion": "FOE",
    "cognitive_complexity": "CXS",
    "circular_import": "CIR",
    "dead_code_accumulation": "DCA",
}

_CHOICES_LABEL = "[t]rue positive  [f]alse positive  [s]kip  [q]uit"


def _abbrev(signal_type: str) -> str:
    return _SIGNAL_ABBREVS.get(str(signal_type).lower(), str(signal_type).upper()[:6])


def review_findings(
    findings: list[Finding],
    feedback_path: Path,
    console: Console,
    repo_root: Path | None = None,
    *,
    calibration_hint_threshold: int = _CALIBRATION_HINT_THRESHOLD,
) -> int:
    """Interactively triage each finding as TP/FP and save feedback.

    Prompts the user with ``[t]rue positive / [f]alse positive / [s]kip / [q]uit``
    for each finding. Verdicts are persisted immediately as :class:`FeedbackEvent`
    entries to *feedback_path*.  After the session a calibration hint is shown
    when the total accumulated count reaches *calibration_hint_threshold*.

    Returns the number of verdicts recorded in this session.
    """
    # Guard: requires an interactive TTY
    if not sys.stdin.isatty():
        console.print("[dim]--review requires an interactive terminal — skipped.[/dim]")
        return 0

    if not findings:
        console.print("[green]No findings to review.[/green]")
        return 0

    from drift.calibration.feedback import FeedbackEvent, load_feedback, record_feedback

    total = len(findings)
    console.print(f"\n[bold]{total} finding(s) to review[/bold] — {_CHOICES_LABEL}\n")

    saved = 0

    for idx, finding in enumerate(findings, start=1):
        file_rel = finding.file_path.as_posix() if finding.file_path else "<unknown>"
        line_info = f":{finding.start_line}" if finding.start_line else ""
        signal_label = _abbrev(finding.signal_type)

        detail = Text()
        detail.append(f"{signal_label}", style="bold cyan")
        detail.append(f"  {file_rel}{line_info}", style="dim")
        detail.append("  score=", style="dim")
        detail.append(f"{finding.score:.2f}", style="yellow")
        detail.append(f"\n{finding.title}")

        console.print(
            Panel(
                detail,
                title=f"[dim]Finding {idx}/{total}[/dim]",
                border_style="blue",
                padding=(0, 1),
            )
        )

        raw = (
            click.prompt(
                "  verdict",
                default="s",
                show_default=False,
                prompt_suffix=" > ",
            )
            .strip()
            .lower()
        )
        choice = raw[:1] if raw else "s"

        if choice == "q":
            console.print("  [dim]Quit.[/dim]")
            break

        if choice in ("t", "f"):
            verdict = "tp" if choice == "t" else "fp"
            event = FeedbackEvent(
                signal_type=str(finding.signal_type),
                file_path=file_rel,
                verdict=verdict,  # type: ignore[arg-type]
                source="user",
                start_line=finding.start_line,
            )
            record_feedback(feedback_path, event)
            label = "True positive" if verdict == "tp" else "False positive"
            console.print(f"  [green]Saved[/green] {label} — {signal_label} {file_rel}{line_info}")
            saved += 1
        else:
            # s or unknown
            console.print("  [dim]Skipped.[/dim]")

        console.print()

    console.print(f"[bold]{saved} verdict(s) saved.[/bold]")

    # Calibration hint when enough evidence has accumulated
    total_events = len(load_feedback(feedback_path))
    if total_events >= calibration_hint_threshold:
        console.print(
            Panel(
                "[bold]Calibration available[/bold] — "
                "run [bold cyan]drift calibrate run[/bold cyan] "
                "to apply adjusted signal weights.",
                border_style="green",
                padding=(0, 1),
            )
        )

    return saved
