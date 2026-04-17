"""Rich terminal output for Drift analysis results."""

from __future__ import annotations

import linecache
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drift.commands import make_console
from drift.finding_rendering import build_first_run_summary
from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType

# Brand accent: Deep Teal (slate/teal palette)
_TEAL = "rgb(13,148,136)"
_TEAL_BOLD = "bold rgb(13,148,136)"

if TYPE_CHECKING:
    from pathlib import Path

    from drift.recommendations import Recommendation
    from drift.timeline import RepoTimeline

# Colors per severity
_SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}

_SEVERITY_ICONS = {
    Severity.CRITICAL: "◉",
    Severity.HIGH: "◉",
    Severity.MEDIUM: "◎",
    Severity.LOW: "○",
    Severity.INFO: "○",
}

_SIGNAL_LABELS: dict[str, str] = {
    SignalType.PATTERN_FRAGMENTATION: "PFS",
    SignalType.ARCHITECTURE_VIOLATION: "AVS",
    SignalType.MUTANT_DUPLICATE: "MDS",
    SignalType.EXPLAINABILITY_DEFICIT: "EDS",
    SignalType.DOC_IMPL_DRIFT: "DIA",
    SignalType.TEMPORAL_VOLATILITY: "TVS",
    SignalType.SYSTEM_MISALIGNMENT: "SMS",
    SignalType.BROAD_EXCEPTION_MONOCULTURE: "BEM",
    SignalType.TEST_POLARITY_DEFICIT: "TPD",
    SignalType.GUARD_CLAUSE_DEFICIT: "GCD",
    SignalType.NAMING_CONTRACT_VIOLATION: "NBV",
    SignalType.BYPASS_ACCUMULATION: "BAT",
    SignalType.EXCEPTION_CONTRACT_DRIFT: "ECM",
    SignalType.CO_CHANGE_COUPLING: "CCC",
    SignalType.TS_ARCHITECTURE: "TSA",
    SignalType.COHESION_DEFICIT: "COD",
    SignalType.MISSING_AUTHORIZATION: "MAZ",
    SignalType.INSECURE_DEFAULT: "ISD",
    SignalType.HARDCODED_SECRET: "HSC",
    SignalType.PHANTOM_REFERENCE: "PHR",
    SignalType.TYPE_SAFETY_BYPASS: "TSB",
    SignalType.FAN_OUT_EXPLOSION: "FOE",
    SignalType.COGNITIVE_COMPLEXITY: "CXS",
    SignalType.CIRCULAR_IMPORT: "CIR",
    SignalType.DEAD_CODE_ACCUMULATION: "DCA",
}

# Human-readable short names shown alongside abbreviations in the findings table.
# Format: abbr → concise English label (max ~16 chars for column fit).
_SIGNAL_SHORT_NAMES: dict[str, str] = {
    "PFS": "Pattern Frag.",
    "AVS": "Arch. Violation",
    "MDS": "Mutant Dupl.",
    "EDS": "Expl. Deficit",
    "DIA": "Doc/Impl Drift",
    "TVS": "Temp. Volatility",
    "SMS": "System Misalign.",
    "BEM": "Broad Exceptions",
    "TPD": "Test Polarity",
    "GCD": "Guard Clauses",
    "NBV": "Naming Contract",
    "BAT": "Bypass Accum.",
    "ECM": "Exception Drift",
    "CCC": "Co-Change",
    "TSA": "TS Architecture",
    "COD": "Cohesion Deficit",
    "MAZ": "Missing Auth.",
    "ISD": "Insecure Default",
    "HSC": "Hardcoded Secret",
    "PHR": "Phantom Ref.",
    "TSB": "Type Safety",
    "FOE": "Fan-out Expl.",
    "CXS": "Cognitive Compl.",
    "CIR": "Circular Import",
    "DCA": "Dead Code",
}

# Signal abbreviations for security findings — these get a dedicated section (ADR-047)
_SECURITY_SIGNAL_ABBREVS: frozenset[str] = frozenset({"MAZ", "HSC", "ISD"})

# --explain: concise signal explanations (why it matters → what to do)
_SIGNAL_EXPLANATIONS: dict[str, tuple[str, str]] = {
    SignalType.PATTERN_FRAGMENTATION: (
        "Multiple divergent implementations of the same pattern"
        " increase maintenance cost and bug surface.",
        "Consolidate into a shared abstraction or utility;"
        " apply the dominant pattern consistently.",
    ),
    SignalType.ARCHITECTURE_VIOLATION: (
        "Dependency flows against the declared layer order, eroding module boundaries.",
        "Move the import to the correct layer or introduce an interface/adapter at the boundary.",
    ),
    SignalType.MUTANT_DUPLICATE: (
        "Near-identical code blocks that diverge slightly — one fix may not reach all copies.",
        "Extract a shared helper or base class; parameterize the differences.",
    ),
    SignalType.EXPLAINABILITY_DEFICIT: (
        "Complex logic lacks comments, docstrings, or clear naming,"
        " making review and onboarding harder.",
        "Add a docstring explaining intent; rename variables to convey purpose.",
    ),
    SignalType.DOC_IMPL_DRIFT: (
        "Documentation and implementation have diverged — readers will be misled.",
        "Update the docstring/README to match current behavior, or fix the code to match the docs.",
    ),
    SignalType.TEMPORAL_VOLATILITY: (
        "File changes unusually often, correlating with higher defect rates.",
        "Stabilize the interface; split volatile logic from stable contracts.",
    ),
    SignalType.SYSTEM_MISALIGNMENT: (
        "Naming conventions, structure, or patterns deviate from the project norm.",
        "Rename to match project conventions; move to the expected package location.",
    ),
    SignalType.BROAD_EXCEPTION_MONOCULTURE: (
        "Bare except or overly broad exception handlers swallow errors silently.",
        "Catch specific exceptions; log or re-raise unexpected ones.",
    ),
    SignalType.TEST_POLARITY_DEFICIT: (
        "Tests only cover happy paths — negative/edge cases are untested.",
        "Add failure-case tests for invalid input, boundary values, and error paths.",
    ),
    SignalType.GUARD_CLAUSE_DEFICIT: (
        "Deep nesting from missing early returns makes the function harder to follow.",
        "Invert conditions and return early to flatten the control flow.",
    ),
    SignalType.COHESION_DEFICIT: (
        "Module or class mixes unrelated responsibilities, increasing coupling.",
        "Split into focused modules: one responsibility per class or file.",
    ),
    SignalType.NAMING_CONTRACT_VIOLATION: (
        "Names violate project conventions (e.g. prefix/suffix rules), confusing readers.",
        "Rename to match the established naming convention.",
    ),
    SignalType.BYPASS_ACCUMULATION: (
        "Growing number of TODO/HACK/FIXME bypasses suggests deferred technical debt.",
        "Resolve the underlying issue or file a tracked ticket and add a link.",
    ),
    SignalType.EXCEPTION_CONTRACT_DRIFT: (
        "Declared and actually raised exceptions diverge — callers may not handle all cases.",
        "Align raises with the documented exception contract.",
    ),
    SignalType.CO_CHANGE_COUPLING: (
        "Files that always change together likely share a hidden dependency.",
        "Extract the shared concern into a module both can import.",
    ),
    SignalType.COGNITIVE_COMPLEXITY: (
        "Function exceeds cognitive complexity threshold, increasing bug risk.",
        "Decompose into smaller helper functions; simplify branching logic.",
    ),
    SignalType.FAN_OUT_EXPLOSION: (
        "Module imports too many other modules, creating fragile coupling.",
        "Introduce a facade or mediator; reduce direct dependencies.",
    ),
    SignalType.CIRCULAR_IMPORT: (
        "Circular imports create fragile load-order dependencies and block refactoring.",
        "Break the cycle with dependency inversion or a shared interface module.",
    ),
    SignalType.DEAD_CODE_ACCUMULATION: (
        "Unreachable code clutters the codebase and misleads readers.",
        "Remove the dead code; rely on version control for history.",
    ),
    SignalType.MISSING_AUTHORIZATION: (
        "Endpoint or sensitive operation lacks an authorization check.",
        "Add an explicit authorization guard before the operation.",
    ),
    SignalType.INSECURE_DEFAULT: (
        "A security-relevant setting defaults to an insecure value.",
        "Change the default to the secure option; require explicit opt-in for weaker settings.",
    ),
    SignalType.HARDCODED_SECRET: (
        "Credentials or secrets are hardcoded in source, risking exposure.",
        "Move to environment variables or a secret manager; rotate the exposed credential.",
    ),
    SignalType.PHANTOM_REFERENCE: (
        "Code references a symbol, module, or path that does not exist.",
        "Remove the stale reference or create the missing target.",
    ),
    SignalType.TYPE_SAFETY_BYPASS: (
        "Explicit type: ignore or cast bypasses the type checker, hiding potential bugs.",
        "Fix the underlying type issue; narrow the ignore to a specific error code if unavoidable.",
    ),
}


def _signal_label(signal_type: str) -> str:
    """Return a stable signal label; fall back to canonical signal id."""
    signal = str(signal_type)
    return _SIGNAL_LABELS.get(signal, signal)


def _signal_display_label(signal_type: str) -> str:
    """Return 'PFS · Pattern Frag.' for table columns; abbr only if unknown."""
    abbr = _signal_label(signal_type)
    short = _SIGNAL_SHORT_NAMES.get(abbr)
    return f"{abbr} · {short}" if short else abbr


_MAX_SNIPPET_LINES: int = 8  # Hard cap per finding; prevents scroll-flooding


def _ascii_only(console: Console | None) -> bool:
    """Return True when the current console should avoid non-ASCII glyphs."""
    return bool(getattr(console, "_drift_ascii_only", False))


def _glyph(console: Console | None, unicode_text: str, ascii_text: str) -> str:
    """Pick a Unicode glyph when supported, else an ASCII fallback."""
    return ascii_text if _ascii_only(console) else unicode_text


def _panel_box(console: Console | None) -> box.Box:
    """Pick a Rich box style that stays readable on legacy Windows terminals."""
    return box.ASCII if _ascii_only(console) else box.ROUNDED


def _table_box(console: Console | None) -> box.Box:
    """Pick a table border style based on terminal glyph support."""
    return box.ASCII if _ascii_only(console) else box.SIMPLE_HEAVY


def _severity_icon(severity: Severity, *, ascii_only: bool = False) -> str:
    """Return a severity icon that stays legible on ASCII-only consoles."""
    if ascii_only:
        return "!" if severity in {Severity.CRITICAL, Severity.HIGH} else "*"
    return _SEVERITY_ICONS.get(severity, "?")


def _parser_failure_files(analysis: RepoAnalysis) -> list[str]:
    """Return sorted parser-failure file paths extracted from degradation events."""
    files: set[str] = set()
    for event in analysis.degradation_events:
        if str(event.get("cause", "")) != "parser_failure":
            continue
        details = event.get("details")
        if isinstance(details, dict):
            file_path = details.get("file")
            if isinstance(file_path, str) and file_path:
                files.add(file_path)
    return sorted(files)


def _render_parser_failure_summary(analysis: RepoAnalysis, console: Console) -> None:
    """Render an explicit parser-failure notice for degraded analyses."""
    if "parser_failure" not in analysis.degradation_causes:
        return

    failed_files = _parser_failure_files(analysis)
    if not failed_files:
        return

    shown = failed_files[:5]
    remainder = len(failed_files) - len(shown)
    suffix = f" (+{remainder} more)" if remainder > 0 else ""
    console.print(
        "  [bold yellow]Parser failures[/bold yellow]: "
        f"{', '.join(shown)}{suffix}",
    )


def _read_code_snippet(
    file_path: Path | None,
    start_line: int | None,
    *,
    end_line: int | None = None,
    context: int = 1,
    max_lines: int = 5,
    repo_root: Path | None = None,
    ascii_only: bool = False,
) -> Text | None:
    """Read a short code snippet from a source file.

    Returns a Rich Text with line numbers, a ``→`` marker on the target
    line(s), and syntax-aware highlighting when possible.  Falls back to
    plain bold/dim rendering if the Syntax widget is unavailable.
    """
    if file_path is None or start_line is None:
        return None

    # Resolve absolute path
    if file_path.is_absolute():
        abs_path = file_path
    elif repo_root:
        abs_path = repo_root / file_path
    else:
        abs_path = file_path
    if not abs_path.is_file():
        return None

    highlight_end = end_line or start_line
    first = max(1, start_line - context)
    last = max(highlight_end + context, start_line + max_lines - 1)

    lines: list[tuple[int, str]] = []
    for lineno in range(first, last + 1):
        line = linecache.getline(str(abs_path), lineno)
        if not line and lineno > highlight_end:
            break
        lines.append((lineno, line.rstrip("\n\r")))

    if not lines:
        return None

    # Enforce hard cap — truncate and add a "more lines" marker
    truncated_count = 0
    if len(lines) > _MAX_SNIPPET_LINES:
        truncated_count = len(lines) - _MAX_SNIPPET_LINES
        lines = lines[:_MAX_SNIPPET_LINES]

    text = Text()
    gutter_width = len(str(lines[-1][0]))
    gutter_sep = "|" if ascii_only else "│"
    more_marker = "..." if ascii_only else "…"
    for lineno, content in lines:
        is_target = start_line <= lineno <= highlight_end
        marker = ">" if ascii_only and is_target else ("→" if is_target else " ")
        text.append(f"  {marker} {lineno:>{gutter_width}} {gutter_sep} ", style="dim")
        text.append(f"{content}\n", style="bold" if is_target else "dim")
    if truncated_count:
        text.append(
            f"  {more_marker} ({truncated_count} more lines - use --no-code to hide snippets)\n",
            style="dim italic",
        )
    return text


def _score_bar(score: float, width: int = 20, *, ascii_only: bool = False) -> Text:
    """Render a score as a colored bar."""
    filled = int(score * width)
    empty = width - filled

    if score >= 0.7:
        color = "red"
    elif score >= 0.4:
        color = "yellow"
    else:
        color = "green"

    full_char = "#" if ascii_only else "█"
    empty_char = "-" if ascii_only else "░"

    bar = Text()
    bar.append(full_char * filled, style=color)
    bar.append(empty_char * empty, style="dim")
    bar.append(f" {score:.2f}", style="bold " + color)
    return bar


def _sparkline(values: list[float], width: int = 20) -> str:
    """Simple ASCII sparkline from a list of floats."""
    if not values:
        return ""
    chars = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    return "".join(chars[int((v - mn) / rng * (len(chars) - 1))] for v in values[-width:])


def _render_phase_timing(analysis: RepoAnalysis, console: Console) -> None:
    phase = analysis.phase_timings or {}
    discover = float(phase.get("discover_seconds", 0.0))
    parse = float(phase.get("parse_seconds", 0.0))
    git = float(phase.get("git_seconds", 0.0))
    signals = float(phase.get("signals_seconds", 0.0))
    output = float(phase.get("output_seconds", 0.0))
    total = float(phase.get("total_seconds", analysis.analysis_duration_seconds))

    console.print(
        Text.assemble(
            ("  Phase timing: ", "dim"),
            (f"discover {discover:.3f}s", "dim"),
            (" | ", "dim"),
            (f"parse {parse:.3f}s", "dim"),
            (" | ", "dim"),
            (f"git {git:.3f}s", "dim"),
            (" | ", "dim"),
            (f"signals {signals:.3f}s", "dim"),
            (" | ", "dim"),
            (f"output {output:.3f}s", "dim"),
            (" | ", "dim"),
            (f"total {total:.3f}s", "dim"),
        ),
    )


def _render_first_run_panel(
    analysis: RepoAnalysis,
    *,
    console: Console,
    language: str | None = None,
) -> None:
    """Render a compact first-run orientation block before deep detail tables."""
    summary = build_first_run_summary(analysis, max_items=3, language=language)
    is_german = (language or "").lower().startswith("de")
    title = "Starte hier" if is_german else "Start Here"
    next_label = "Naechster Schritt" if is_german else "Next step"

    body = Text()
    body.append(summary["headline"], style="bold")
    body.append("\n")
    body.append(summary["why_this_matters"], style="dim")

    top_findings = summary["top_findings"]
    if top_findings:
        body.append("\n\n")
        for index, finding in enumerate(top_findings, start=1):
            signal = finding.get("signal_abbrev") or finding.get("signal") or "?"
            title_text = finding.get("title") or ""
            location = finding.get("file") or "repo"
            line = finding.get("line")
            suffix = f":{line}" if line else ""
            body.append(f"{index}. [{signal}] {title_text}\n", style="bold")
            body.append(f"   {location}{suffix}\n", style="dim")

    body.append("\n")
    body.append(f"{next_label}: ", style=_TEAL_BOLD)
    body.append(summary["next_step"], style=_TEAL)

    console.print(
        Panel(
            body,
            title=f"[bold]{title}[/bold]",
            border_style=_TEAL,
            box=_panel_box(console),
        ),
    )


def _render_first_run_next_steps(
    analysis: RepoAnalysis,
    *,
    console: Console,
    language: str | None = None,
) -> None:
    """Render a compact next-steps panel for first-run mode."""
    is_german = (language or "").lower().startswith("de")
    total = len(analysis.findings)
    dash = " - " if _ascii_only(console) else " — "

    if is_german:
        title = "Naechste Schritte"
        lines = [
            f"[bold]{total}[/bold] Befunde erkannt{dash}oben sind die wichtigsten 3.",
            "",
            f"[bold]1.[/bold] drift setup          {dash}Konfiguration erstellen",
            f"[bold]2.[/bold] drift analyze         {dash}Alle Befunde anzeigen",
            f"[bold]3.[/bold] drift mcp --serve     {dash}KI-Agent-Integration starten",
            f"[bold]4.[/bold] drift check --fail-on high  {dash}Als CI-Gate verwenden",
        ]
    else:
        lines = [
            f"[bold]{total}[/bold] findings detected{dash}the top 3 are shown above.",
            "",
            f"[bold]1.[/bold] drift setup          {dash}generate a config file",
            f"[bold]2.[/bold] drift analyze         {dash}see all findings",
            f"[bold]3.[/bold] drift mcp --serve     {dash}start AI agent integration",
            f"[bold]4.[/bold] drift check --fail-on high  {dash}use as CI gate",
        ]
        title = "Next Steps"

    body = Text.from_markup("\n".join(lines))
    console.print(
        Panel(
            body,
            title=f"[bold]{title}[/bold]",
            border_style=_TEAL,
            box=_panel_box(console),
        ),
    )


def render_summary(
    analysis: RepoAnalysis,
    console: Console | None = None,
    *,
    language: str | None = None,
) -> None:
    """Render the top-level analysis summary."""
    if console is None:
        console = make_console()

    ascii_only = _ascii_only(console)

    console.print()
    header_color = _SEVERITY_COLORS.get(analysis.severity, "white")

    grade_letter, grade_label = analysis.grade
    grade_sep = " - " if ascii_only else " — "
    info_sep = "  |  " if ascii_only else "  │  "
    range_text = "0.30-0.65" if ascii_only else "0.30–0.65"
    grade_text = f"  Grade {grade_letter}{grade_sep}{grade_label}"
    first_run_hint = f"{info_sep}Typical first-run range: {range_text}"

    trend = analysis.trend
    if trend and trend.direction != "baseline" and trend.delta is not None:
        arrow = (
            "v" if ascii_only and trend.direction == "improving"
            else "^" if ascii_only and trend.direction == "degrading"
            else "->" if ascii_only
            else "↓" if trend.direction == "improving"
            else "↑" if trend.direction == "degrading"
            else "→"
        )
        delta_color = (
            _TEAL if trend.direction == "improving"
            else "red" if trend.direction == "degrading"
            else "dim"
        )
        trend_parts: tuple[tuple[str, str], ...] = (
            ("  ", ""),
            (f"delta {trend.delta:+.3f} {arrow} {trend.direction}", delta_color),
        )
    else:
        trend_parts = (("  - baseline", "dim"),)

    console.print(
        Panel(
            Text.assemble(
                ("DRIFT SCORE  ", "bold"),
                (f"{analysis.drift_score:.2f}", f"bold {header_color}"),
                (grade_text, f"bold {header_color}"),
                (first_run_hint, "dim"),
                *trend_parts,
                (info_sep, "dim"),
                (f"{analysis.total_files} files", ""),
                (info_sep, "dim"),
                (f"{analysis.total_functions} functions", ""),
                (info_sep, "dim"),
                (f"AI: {analysis.ai_attributed_ratio:.0%}", ""),
                *(
                    (
                        (" (", "dim"),
                        (", ".join(analysis.ai_tools_detected), "dim italic"),
                        (")", "dim"),
                    )
                    if analysis.ai_tools_detected
                    else ()
                ),
                *(
                    ((info_sep, "dim"), (f"{analysis.suppressed_count} suppressed", "dim italic"))
                    if analysis.suppressed_count
                    else ()
                ),
                *(
                    (
                        (info_sep, "dim"),
                        (f"{analysis.context_tagged_count} ctx-tagged", "dim italic"),
                    )
                    if analysis.context_tagged_count
                    else ()
                ),
                (info_sep, "dim"),
                (f"{analysis.analysis_duration_seconds:.1f}s", "dim"),
                (info_sep, "dim"),
                (
                    "DEGRADED" if analysis.is_degraded else "COMPLETE",
                    "bold yellow" if analysis.is_degraded else "bold green",
                ),
            ),
            title=f"[bold]drift analyze[/bold]  {analysis.repo_path}",
            border_style=header_color,
            box=_panel_box(console),
        ),
    )

    if analysis.is_degraded:
        causes = ", ".join(analysis.degradation_causes) or "unknown"
        components = ", ".join(analysis.degradation_components) or "unknown"
        console.print(
            f"  [bold yellow]Analysis degraded[/bold yellow]: causes={causes}; "
            f"components={components}",
        )
        _render_parser_failure_summary(analysis, console)

    _render_phase_timing(analysis, console)

    warn_icon = _glyph(console, "⚠", "!")
    right_arrow = _glyph(console, "→", "->")
    le_op = "<=" if ascii_only else "≤"
    dash = " - " if ascii_only else " — "

    expired_suppression_count = analysis.expired_suppression_count or len(
        analysis.expired_suppressions
    )
    if expired_suppression_count:
        console.print(
            f"  [bold yellow]{warn_icon} {expired_suppression_count} suppression(s) "
            "have expired and their findings are now re-active.[/bold yellow]"
        )

    if analysis.skipped_languages:
        summary = ", ".join(
            f"{lang} ({n})" for lang, n in sorted(analysis.skipped_languages.items())
        )
        console.print(
            Text.assemble(
                (f"  {warn_icon} Skipped ", "bold yellow"),
                (f"{sum(analysis.skipped_languages.values())} file(s)", "bold yellow"),
                (f": {summary}. ", ""),
                ("Install: ", ""),
                ("pip install drift-analyzer[typescript]", "bold"),
            ),
        )

    if trend and trend.recent_scores and trend.direction != "baseline":
        sep = " -> " if ascii_only else " → "
        scores_str = sep.join(f"{s:.3f}" for s in trend.recent_scores)
        depth = trend.history_depth
        sfx = "s" if depth != 1 else ""
        console.print(f"  [dim]Trend: {scores_str} ({depth} snapshot{sfx})[/dim]")
    elif trend and trend.direction == "baseline":
        console.print(
            f"  [dim]{warn_icon} Run drift analyze again after structural "
            "changes to establish trend.[/dim]",
        )

    if analysis.drift_score > 0.30:
        console.print(
            f"  [dim]{right_arrow} Score {analysis.drift_score:.2f} above target"
            f" ({le_op} 0.30){dash}run [bold]drift fix-plan --max-tasks 3[/bold]"
            " for prioritized next steps.[/dim]"
        )
    else:
        ok_text = "[ok]" if ascii_only else "✓"
        console.print(
            f"  [dim]{right_arrow} Score {analysis.drift_score:.2f}"
            f" at or below target ({le_op} 0.30) {ok_text}[/dim]"
        )

    if 0 < analysis.total_files < 20:
        console.print(
            f"  [dim]{warn_icon} Small repo ({analysis.total_files} files){dash}"
            "signal precision improves with 20+ files. "
            "Results are indicative, not definitive.[/dim]"
        )

    console.print()
    _render_first_run_panel(analysis, console=console, language=language)


def render_module_table(analysis: RepoAnalysis, console: Console | None = None) -> None:
    """Render the module ranking table."""
    if console is None:
        console = Console()

    if not analysis.module_scores:
        console.print("[dim]No modules to display.[/dim]")
        return

    table = Table(title="Module Drift Ranking", show_lines=False, pad_edge=False)
    table.add_column("Module", style="bold", min_width=30)
    table.add_column("Score", justify="right", min_width=8)
    table.add_column("Bar", min_width=25)
    table.add_column("Findings", justify="right")
    table.add_column("Top Signal", min_width=10)

    for ms in analysis.module_scores[:15]:
        color = _SEVERITY_COLORS.get(ms.severity, "white")
        bar = _score_bar(ms.drift_score)

        top_signal = ""
        if ms.signal_scores:
            top = max(ms.signal_scores, key=lambda s: ms.signal_scores[s])
            top_signal = f"{_signal_label(top)} {ms.signal_scores[top]:.2f}"

        table.add_row(
            ms.path.as_posix() + "/",
            Text(f"{ms.drift_score:.2f}", style=color),
            bar,
            str(len(ms.findings)),
            top_signal,
        )

    console.print(table)


def _format_finding_detail(
    f: Finding,
    *,
    repo_root: Path | None = None,
    show_code: bool = True,
    explain: bool = False,
) -> Text:
    """Build the detail body for a single finding panel."""
    color = _SEVERITY_COLORS.get(f.severity, "white")
    signal_label = _signal_label(f.signal_type)
    text = Text()

    # Title: [SIGNAL] Description (score)
    text.append(f"[{signal_label}] {f.title} ({f.score:.2f})\n", style=f"bold {color}")

    # Primary location (with terminal hyperlink if absolute path resolvable)
    if f.file_path:
        loc = f.file_path.as_posix()
        if f.start_line:
            loc += f":{f.start_line}"
        abs_path = (
            (repo_root / f.file_path).resolve()
            if repo_root and not f.file_path.is_absolute()
            else f.file_path.resolve()
        )
        link_uri = abs_path.as_uri()
        text.append("  → ", style="dim")
        text.append(loc, style=f"dim link {link_uri}")
        text.append("\n")

    # Code snippet with end_line support
    if show_code and f.file_path and f.start_line:
        snippet = _read_code_snippet(
            f.file_path,
            f.start_line,
            end_line=f.end_line,
            repo_root=repo_root,
        )
        if snippet is not None:
            text.append_text(snippet)

    # All related files (Opt-2: show them all, cap at 10 + remainder note)
    if f.related_files:
        shown = f.related_files[:10]
        for rf in shown:
            abs_rf = (
                (repo_root / rf).resolve()
                if repo_root and not rf.is_absolute()
                else rf.resolve()
            )
            rf_link = abs_rf.as_uri()
            text.append("  → ", style="dim")
            text.append(rf.as_posix(), style=f"dim link {rf_link}")
            text.append("\n")
        remainder = len(f.related_files) - len(shown)
        if remainder > 0:
            text.append(f"  … and {remainder} more\n", style="dim italic")

    # Description (first line only in compact view)
    first_line = f.description.splitlines()[0] if f.description else ""
    if first_line:
        text.append(f"  {first_line}\n", style="dim")

    # Next-action line — imperative, concrete
    if f.fix:
        text.append("  → Next: ", style=_TEAL_BOLD)
        text.append(f"{f.fix}\n", style=_TEAL)

    # Context tags (ADR-006)
    ctx_tags = f.metadata.get("context_tags")
    if ctx_tags:
        text.append(f"  [ctx: {', '.join(ctx_tags)}]\n", style="cyan italic")

    # Deliberate-pattern disambiguation (EPISTEMICS §1/§3)
    dpr = f.metadata.get("deliberate_pattern_risk")
    if dpr:
        text.append(f"  ⚠ {dpr}\n", style="dim italic")

    # Causal attribution (ADR-034)
    if f.attribution:
        a = f.attribution
        short_hash = a.commit_hash[:7] if a.commit_hash else "?"
        date_str = a.date.isoformat() if a.date else "?"
        parts = [f"Commit {short_hash}", a.author, date_str]
        if a.branch_hint:
            parts.append(a.branch_hint)
        attr_line = " · ".join(parts)
        if a.ai_attributed:
            attr_line += " [AI]"
        text.append(f"  ╰─ {attr_line}\n", style="dim cyan")

    # --explain: contextual explanation panel
    if explain:
        explanation = _SIGNAL_EXPLANATIONS.get(f.signal_type)
        if explanation:
            why, action = explanation
            text.append("  ┌─ Why: ", style="bold dim")
            text.append(f"{why}\n", style="dim")
            text.append("  └─ Action: ", style="bold dim")
            text.append(f"{action}\n", style="dim")

    return text


def render_findings(
    findings: list[Finding],
    max_items: int = 20,
    console: Console | None = None,
    sort_by: str = "impact",
    *,
    repo_root: Path | None = None,
    show_code: bool = True,
    explain: bool = False,
    group_by: str | None = None,
) -> None:
    """Render a list of findings with fix recommendations and all locations."""
    if console is None:
        console = Console()

    if not findings:
        console.print("[green]No findings.[/green]")
        return

    if sort_by == "score":
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                -f.score,
                f.signal_type,
                f.file_path.as_posix() if f.file_path else "",
                f.start_line or 0,
            ),
        )
    else:
        # Sort by impact if available, fall back to score
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                -(f.impact if f.impact > 0 else f.score),
                f.signal_type,
                f.file_path.as_posix() if f.file_path else "",
                f.start_line or 0,
            ),
        )

    if group_by:
        from drift.output.grouping import group_findings

        groups = group_findings(sorted_findings, group_by)
        total_shown = 0
        for group_name, group_items in groups.items():
            if total_shown >= max_items:
                break
            budget = max_items - total_shown
            _render_findings_table(
                group_items[:budget],
                console,
                title=f"Findings — {group_by}: {group_name}",
                repo_root=repo_root,
                show_code=show_code,
                explain=explain,
            )
            total_shown += min(len(group_items), budget)
            remaining_in_group = len(group_items) - budget
            if remaining_in_group > 0:
                console.print(
                    f"[dim]... and {remaining_in_group} more "
                    f"in {group_name}[/dim]"
                )
            console.print()

        remaining = len(sorted_findings) - max_items
        if remaining > 0:
            console.print(
                f"[dim]... {remaining} more findings not shown "
                f"(increase --max-findings)[/dim]"
            )
        return

    # Render dedicated security section before the main findings table (ADR-047)
    _render_security_section(
        sorted_findings,
        console,
        repo_root=repo_root,
        show_code=show_code,
    )

    _render_findings_table(
        sorted_findings[:max_items],
        console,
        title="Findings",
        repo_root=repo_root,
        show_code=show_code,
        explain=explain,
    )

    remaining = len(sorted_findings) - max_items
    if remaining > 0:
        console.print(f"[dim]... and {remaining} more findings[/dim]")


def _render_security_section(
    findings: list[Finding],
    console: Console,
    *,
    repo_root: Path | None = None,
    show_code: bool = True,
) -> bool:
    """Render a dedicated security findings panel (ADR-047).

    Returns True if any security findings were rendered.
    """
    security = [
        f for f in findings
        if _signal_label(f.signal_type) in _SECURITY_SIGNAL_ABBREVS
    ]
    if not security:
        return False

    table = Table(title="Security Findings", show_lines=True, border_style="bold red")
    table.add_column("", width=2)
    table.add_column("Signal", min_width=20)
    table.add_column("Score", justify="right", min_width=6)
    table.add_column("Title / Details", min_width=50)

    for f in security:
        icon = _SEVERITY_ICONS.get(f.severity, "?")
        color = _SEVERITY_COLORS.get(f.severity, "white")
        signal = _signal_display_label(f.signal_type)
        table.add_row(
            Text(icon, style=color),
            signal,
            Text(f"{f.score:.2f}", style=color),
            _format_finding_detail(f, repo_root=repo_root, show_code=show_code),
        )

    console.print(table)
    return True


def _render_findings_table(
    items: list[Finding],
    console: Console,
    *,
    title: str = "Findings",
    repo_root: Path | None = None,
    show_code: bool = True,
    explain: bool = False,
) -> None:
    """Render a Rich table for a list of findings."""
    table = Table(title=title, show_lines=True)
    table.add_column("", width=2)
    table.add_column("Signal", min_width=20)
    table.add_column("Score", justify="right", min_width=6)
    table.add_column("Title / Details", min_width=50)

    for f in items:
        icon = _SEVERITY_ICONS.get(f.severity, "?")
        color = _SEVERITY_COLORS.get(f.severity, "white")
        signal = _signal_display_label(f.signal_type)

        table.add_row(
            Text(icon, style=color),
            signal,
            Text(f"{f.score:.2f}", style=color),
            _format_finding_detail(
                f, repo_root=repo_root, show_code=show_code, explain=explain
            ),
        )

    console.print(table)


def render_module_detail(module: ModuleScore, console: Console | None = None) -> None:
    """Render detailed view for a single module."""
    if console is None:
        console = Console()

    color = _SEVERITY_COLORS.get(module.severity, "white")
    console.print()
    console.print(
        Panel(
            _format_module_detail(module),
            title=f"[bold]{module.path.as_posix()}/[/bold]",
            border_style=color,
        ),
    )


def _format_module_detail(module: ModuleScore) -> Text:
    """Build detail text for a module panel."""
    text = Text()
    text.append(f"Drift Score: {module.drift_score:.2f}", style="bold")
    text.append(f"  ({module.severity.value.upper()})\n\n", style="dim")

    for sig_type, score in sorted(module.signal_scores.items(), key=lambda x: x[1], reverse=True):
        label = _signal_label(sig_type)
        bar = "█" * int(score * 15) + "░" * (15 - int(score * 15))

        color = "green"
        if score >= 0.7:
            color = "red"
        elif score >= 0.4:
            color = "yellow"

        text.append(f"  {label}  ", style="bold")
        text.append(f"{bar}", style=color)
        text.append(f"  {score:.2f}\n")

    if module.findings:
        text.append("\nTop Findings:\n", style="bold")
        for f in sorted(module.findings, key=lambda x: x.score, reverse=True)[:5]:
            icon = _SEVERITY_ICONS.get(f.severity, "?")
            text.append(f"  {icon} ", style=_SEVERITY_COLORS.get(f.severity, "white"))
            text.append(f"{f.title}\n")

    return text


def _render_guidance_footer(console: Console, *, language: str | None = None) -> None:
    """Render a subtle 'what's next' footer for unconfigured repos."""
    is_german = (language or "").lower().startswith("de")
    if is_german:
        title = "Naechste Schritte"
        lines = [
            "[bold]1.[/bold] drift init              — Konfiguration erstellen",
            "[bold]2.[/bold] drift init --mcp         — KI-Agent-Integration aktivieren",
            "[bold]3.[/bold] drift init --ci           — CI-Gate einrichten",
            "[bold]4.[/bold] drift trend              — Delta ueber Zeit verfolgen",
        ]
    else:
        title = "What's Next"
        lines = [
            "[bold]1.[/bold] drift init              — create a drift.yaml config",
            "[bold]2.[/bold] drift init --mcp         — enable AI agent integration",
            "[bold]3.[/bold] drift init --ci           — set up CI gate",
            "[bold]4.[/bold] drift trend              — track changes over time",
        ]
    body = Text.from_markup("\n".join(lines))
    console.print()
    console.print(Panel(body, title=f"[dim bold]{title}[/dim bold]", border_style="dim"))


def render_full_report(
    analysis: RepoAnalysis,
    console: Console | None = None,
    sort_by: str = "impact",
    max_findings: int = 20,
    *,
    show_code: bool = True,
    explain: bool = False,
    language: str | None = None,
    group_by: str | None = None,
    first_run: bool = False,
) -> None:
    """Render the complete analysis report."""
    if console is None:
        console = Console()

    render_summary(analysis, console, language=language)
    console.print()

    if first_run:
        _render_first_run_next_steps(analysis, console=console, language=language)
        return

    render_module_table(analysis, console)
    console.print()
    render_findings(
        analysis.findings,
        max_items=max_findings,
        console=console,
        sort_by=sort_by,
        repo_root=analysis.repo_path,
        show_code=show_code,
        explain=explain,
        group_by=group_by,
    )

    # Interpretation guidance footer
    console.print()
    console.print(
        Panel(
            "[dim]The drift score measures structural entropy, not code quality. "
            "A rising score signals coherence loss — but temporary increases "
            "during migrations or refactorings are expected.\n"
            "Deliberate polymorphism (Strategy, Adapter, Plugin patterns) can "
            "trigger MDS/PFS findings that reflect correct design, not erosion.\n"
            "Use [bold]drift trend[/bold] to track deltas over time. "
            "Interpret single snapshots with caution.[/dim]",
            title="[dim bold]Interpretation[/dim bold]",
            border_style=_TEAL,
        ),
    )

    # Guidance footer for unconfigured repos — show actionable next steps
    _repo_root = analysis.repo_path
    if (
        _repo_root
        and not (_repo_root / "drift.yaml").exists()
        and not (_repo_root / ".drift").exists()
    ):
        _render_guidance_footer(console, language=language)


# ---------------------------------------------------------------------------
# Timeline rendering
# ---------------------------------------------------------------------------


def render_timeline(
    timeline: RepoTimeline,
    console: Console | None = None,
) -> None:
    """Render the drift timeline showing *when* and *why* drift began."""
    if console is None:
        console = Console()

    if not timeline.module_timelines:
        console.print("[dim]No timeline data — no modules with findings.[/dim]")
        return

    # AI burst summary
    if timeline.ai_burst_periods:
        console.print()
        console.print("[bold]AI Commit Bursts[/bold]")
        for burst in timeline.ai_burst_periods:
            span = burst.end_date - burst.start_date
            console.print(
                f"  [red]●[/red] {burst.start_date} → {burst.end_date} "
                f"({span.days + 1}d): "
                f"[bold]{burst.ai_commit_count}[/bold] AI commits "
                f"/ {burst.commit_count} total, "
                f"{len(burst.files_affected)} files",
            )
        console.print()

    # Per-module timelines
    table = Table(title="Module Drift Timeline", show_lines=True)
    table.add_column("Module", style="bold", min_width=20)
    table.add_column("Clean Until", min_width=12)
    table.add_column("Drift Started", min_width=12)
    table.add_column("Trigger Commits", justify="right")
    table.add_column("AI Burst?", min_width=8)
    table.add_column("Score", justify="right")

    for mt in timeline.module_timelines[:15]:
        clean = str(mt.clean_until) if mt.clean_until else "[dim]—[/dim]"
        started = f"[red]{mt.drift_started}[/red]" if mt.drift_started else "[dim]—[/dim]"
        triggers = str(len(mt.trigger_commits))
        burst_label = "[red]yes[/red]" if mt.ai_burst else "[dim]no[/dim]"
        color = (
            "red" if mt.current_score >= 0.6 else ("yellow" if mt.current_score >= 0.3 else "green")
        )
        score = f"[{color}]{mt.current_score:.2f}[/{color}]"

        table.add_row(mt.module_path, clean, started, triggers, burst_label, score)

    console.print(table)

    # Detailed trigger commits for top 3 drifting modules
    console.print()
    for mt in timeline.module_timelines[:3]:
        if not mt.trigger_commits:
            continue
        console.print(f"[bold]{mt.module_path}/[/bold] — trigger commits:")
        for evt in mt.trigger_commits[:5]:
            ai_tag = " [red](AI)[/red]" if evt.is_ai else ""
            console.print(
                f"  {evt.date}  "
                f"[dim]{evt.commit_hash or '?'}[/dim]  "
                f"{evt.author or '?'}{ai_tag}  "
                f"{evt.description}",
            )
        remaining = len(mt.trigger_commits) - 5
        if remaining > 0:
            console.print(f"  [dim]... +{remaining} more[/dim]")
        console.print()


# ---------------------------------------------------------------------------
# Recommendations rendering
# ---------------------------------------------------------------------------


def render_recommendations(
    recommendations: list[Recommendation],
    console: Console | None = None,
) -> None:
    """Render actionable recommendations."""
    if console is None:
        console = Console()

    if not recommendations:
        console.print("[green]No recommendations — codebase is clean![/green]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]{len(recommendations)} Recommendations[/bold]",
            border_style=_TEAL,
        ),
    )

    impact_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    effort_labels = {
        "low": "[green]low[/green]",
        "medium": "[yellow]med[/yellow]",
        "high": "[red]high[/red]",
    }

    for i, rec in enumerate(recommendations, 1):
        impact_icon = impact_icons.get(rec.impact, "?")
        effort_label = effort_labels.get(rec.effort, rec.effort)
        file_hint = f"  [dim]{rec.file_path.as_posix()}[/dim]" if rec.file_path else ""

        console.print(f"  {impact_icon} [bold]{i}. {rec.title}[/bold]{file_hint}")
        console.print(f"     {rec.description}")
        console.print(f"     Effort: {effort_label}  |  Impact: {rec.impact}")
        console.print()


# ---------------------------------------------------------------------------
# Trend chart rendering
# ---------------------------------------------------------------------------


def render_trend_chart(
    snapshots: list[dict],
    width: int = 60,
    console: Console | None = None,
) -> None:
    """Render an ASCII trend chart of drift scores over time."""
    if console is None:
        console = Console()

    if len(snapshots) < 2:
        console.print("[dim]Need at least 2 snapshots for a chart.[/dim]")
        return

    scores = [s["drift_score"] for s in snapshots]
    dates = [s["timestamp"][:10] for s in snapshots]

    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score if max_score != min_score else 0.1

    # Chart height
    height = 12
    chart_width = min(width, len(scores))

    # Resample if we have more snapshots than chart width
    if len(scores) > chart_width:
        step = len(scores) / chart_width
        sampled_scores = [scores[int(i * step)] for i in range(chart_width)]
        sampled_dates = [dates[int(i * step)] for i in range(chart_width)]
    else:
        sampled_scores = scores
        sampled_dates = dates
        chart_width = len(scores)

    console.print()
    console.print("[bold]Drift Score Trend[/bold]")
    console.print()

    # Render chart rows top-down
    for row in range(height, -1, -1):
        threshold = min_score + (row / height) * score_range
        label = f"{threshold:.2f} │"
        line = []
        for s in sampled_scores:
            normalized = (s - min_score) / score_range
            bar_height = normalized * height
            if bar_height >= row:
                if s >= 0.6:
                    line.append("[red]█[/red]")
                elif s >= 0.3:
                    line.append("[yellow]█[/yellow]")
                else:
                    line.append("[green]█[/green]")
            else:
                line.append(" ")
        console.print(f"  {label}{''.join(line)}")

    # X-axis
    axis = "─" * chart_width
    console.print(f"       └{axis}")

    # Date labels
    if len(sampled_dates) >= 2:
        first_date = sampled_dates[0]
        last_date = sampled_dates[-1]
        padding = chart_width - len(first_date) - len(last_date)
        if padding > 0:
            console.print(f"        {first_date}{' ' * padding}{last_date}")
        else:
            console.print(f"        {first_date}  ...  {last_date}")
    console.print()
