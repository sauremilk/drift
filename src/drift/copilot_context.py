"""Generate Copilot instructions from drift analysis results.

Produces a Markdown section with architectural constraints derived from
drift findings.  The section is framed by merge markers so it can be
safely inserted into an existing ``copilot-instructions.md`` file without
destroying hand-written content.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from drift.api_helpers import signal_abbrev
from drift.models import Finding, RepoAnalysis, SignalType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER_BEGIN = "<!-- drift:begin -- auto-generated architectural constraints from drift -->"
MARKER_END = "<!-- drift:end -->"

# Signals that translate into actionable Copilot instructions.
# Temporal / correlation-based signals are excluded because they can't
# be expressed as "do / don't" rules.
_ACTIONABLE_SIGNALS: frozenset[SignalType] = frozenset({
    SignalType.ARCHITECTURE_VIOLATION,
    SignalType.PATTERN_FRAGMENTATION,
    SignalType.NAMING_CONTRACT_VIOLATION,
    SignalType.GUARD_CLAUSE_DEFICIT,
    SignalType.BROAD_EXCEPTION_MONOCULTURE,
    SignalType.DOC_IMPL_DRIFT,
    SignalType.MUTANT_DUPLICATE,
    SignalType.EXPLAINABILITY_DEFICIT,
    SignalType.BYPASS_ACCUMULATION,
    SignalType.EXCEPTION_CONTRACT_DRIFT,
})

# Minimum score for a finding to be considered
_MIN_SCORE = 0.4
# A signal must appear in at least this many findings to generate a rule
_MIN_FINDING_COUNT = 2


# ---------------------------------------------------------------------------
# Instruction generation
# ---------------------------------------------------------------------------


def _heading(title: str, signal: SignalType) -> str:
    """Build a section heading that includes the canonical signal ID."""
    return f"### {title} ({signal_abbrev(signal)})"


def _format_rule(signal: SignalType, findings: list[Finding]) -> str | None:
    """Produce a Markdown rule block for one signal type.

    Returns *None* if the findings don't yield a useful instruction.
    """
    if not findings:
        return None

    # Group by file to show affected locations
    files = Counter(
        f.file_path.as_posix() for f in findings if f.file_path
    )
    top_files = [fp for fp, _ in files.most_common(5)]

    # Use the first finding's fix as the canonical remediation
    fix = next((f.fix for f in findings if f.fix), None)
    desc = findings[0].description

    lines: list[str] = []

    if signal == SignalType.ARCHITECTURE_VIOLATION:
        lines.append(_heading("Layer Boundaries", signal))
        for f in findings[:5]:
            if f.fix:
                lines.append(f"- {f.fix}")
            elif f.description:
                lines.append(f"- {f.title}: {f.description}")
    elif signal == SignalType.PATTERN_FRAGMENTATION:
        lines.append(_heading("Code Pattern Consistency", signal))
        for f in findings[:5]:
            if f.fix:
                lines.append(f"- {f.fix}")
            else:
                lines.append(f"- {f.title}")
    elif signal == SignalType.NAMING_CONTRACT_VIOLATION:
        lines.append(_heading("Naming Conventions", signal))
        for f in findings[:5]:
            if f.fix:
                lines.append(f"- {f.fix}")
            else:
                lines.append(f"- {f.title}")
    elif signal == SignalType.GUARD_CLAUSE_DEFICIT:
        lines.append(_heading("Input Validation", signal))
        lines.append(
            "- Public functions must validate inputs with guard clauses "
            "before processing."
        )
        if top_files:
            lines.append(f"- Priority modules: {', '.join(f'`{f}`' for f in top_files[:3])}")
    elif signal == SignalType.BROAD_EXCEPTION_MONOCULTURE:
        lines.append(_heading("Exception Handling", signal))
        lines.append(
            "- Use specific exception types instead of bare `except Exception`. "
            "Re-raise or convert to domain exceptions."
        )
        if top_files:
            lines.append(f"- Priority modules: {', '.join(f'`{f}`' for f in top_files[:3])}")
    elif signal == SignalType.DOC_IMPL_DRIFT:
        lines.append(_heading("Documentation Alignment", signal))
        lines.append(
            "- Keep README and architectural documentation in sync with implementation."
        )
        for f in findings[:3]:
            if f.description:
                lines.append(f"- {f.title}")
    elif signal == SignalType.MUTANT_DUPLICATE:
        lines.append(_heading("Deduplication", signal))
        lines.append(
            "- Before creating a new function, check for near-duplicates in the same file. "
            "Extract common logic into shared helpers."
        )
        if top_files:
            lines.append(f"- Files with duplicates: {', '.join(f'`{f}`' for f in top_files[:3])}")
    elif signal == SignalType.EXPLAINABILITY_DEFICIT:
        lines.append(_heading("Code Documentation", signal))
        lines.append(
            "- Complex functions (cyclomatic complexity >10) must have docstrings "
            "and complete type annotations."
        )
        if top_files:
            lines.append(f"- Priority: {', '.join(f'`{f}`' for f in top_files[:3])}")
    elif signal == SignalType.BYPASS_ACCUMULATION:
        lines.append(_heading("TODO/FIXME Hygiene", signal))
        lines.append(
            "- Do not add `# TODO`, `# FIXME`, `# HACK` markers without a linked "
            "issue or timeline. Resolve existing bypass markers before adding new ones."
        )
    elif signal == SignalType.EXCEPTION_CONTRACT_DRIFT:
        lines.append(_heading("Exception Contracts", signal))
        for f in findings[:3]:
            if f.fix:
                lines.append(f"- {f.fix}")
            elif f.description:
                lines.append(f"- {f.title}")
    else:
        # Generic fallback
        lines.append(_heading(signal.value.replace("_", " ").title(), signal))
        if fix:
            lines.append(f"- {fix}")
        elif desc:
            lines.append(f"- {desc}")

    return "\n".join(lines) if lines else None


def generate_instructions(analysis: RepoAnalysis) -> str:
    """Generate a Markdown section with Copilot instructions from analysis results.

    Only actionable signals with sufficient severity/frequency are included.
    """
    # Filter findings to actionable signals above threshold
    actionable: dict[SignalType, list[Finding]] = {}
    for f in analysis.findings:
        if f.signal_type in _ACTIONABLE_SIGNALS and f.score >= _MIN_SCORE:
            actionable.setdefault(f.signal_type, []).append(f)

    # Only keep signals with enough findings
    actionable = {s: fs for s, fs in actionable.items() if len(fs) >= _MIN_FINDING_COUNT}

    if not actionable:
        return _wrap_markers(
            "## Architectural Constraints (drift-generated)\n\n"
            "No significant architectural issues detected. Drift score: "
            f"{analysis.drift_score:.2f} ({analysis.severity.value}).\n"
        )

    sections: list[str] = []
    sections.append("## Architectural Constraints (drift-generated)\n")

    # Sort by finding count descending for priority
    for signal in sorted(actionable, key=lambda s: len(actionable[s]), reverse=True):
        rule = _format_rule(signal, actionable[signal])
        if rule:
            sections.append(rule)

    # Status footer
    sections.append("")
    sections.append("### Current Drift Status")
    sections.append(f"- **Drift Score**: {analysis.drift_score:.2f} ({analysis.severity.value})")
    if analysis.trend:
        direction = analysis.trend.direction
        delta = analysis.trend.delta
        sections.append(f"- **Trend**: {direction}" + (f" (delta {delta:+.2f})" if delta else ""))
    if analysis.module_scores:
        worst = max(analysis.module_scores, key=lambda m: m.drift_score)
        sections.append(
            f"- **Most eroded module**: `{worst.path.as_posix()}` "
            f"(score: {worst.drift_score:.2f})"
        )

    # Cross-reference: security/anti-pattern context
    sections.append("")
    sections.append("### Security & Anti-Pattern Context")
    sections.append(
        "For security findings and anti-pattern rules (e.g. hardcoded secrets, "
        "missing authorization), run:"
    )
    sections.append("")
    sections.append("    drift export-context --format prompt")
    sections.append("")
    sections.append(
        "Combine both outputs for complete architectural + security guidance."
    )

    return _wrap_markers("\n".join(sections) + "\n")


def _wrap_markers(content: str) -> str:
    """Wrap content in drift merge markers."""
    return f"{MARKER_BEGIN}\n{content}{MARKER_END}\n"


# ---------------------------------------------------------------------------
# File I/O with marker-based merge
# ---------------------------------------------------------------------------


def _fingerprint(content: str) -> str:
    """SHA-256 hex digest of content for change detection."""
    return hashlib.sha256(content.encode()).hexdigest()


def merge_into_file(
    target: Path,
    drift_section: str,
    *,
    no_merge: bool = False,
) -> bool:
    """Write or merge drift instructions into the target file.

    Returns True if the file was actually modified, False if unchanged.
    """
    if no_merge or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(drift_section, encoding="utf-8")
        return True

    existing = target.read_text(encoding="utf-8")

    begin_idx = existing.find(MARKER_BEGIN)
    end_idx = existing.find(MARKER_END)

    if begin_idx >= 0 and end_idx >= 0:
        # Replace between markers (inclusive)
        end_idx += len(MARKER_END)
        # Consume trailing newline if present
        if end_idx < len(existing) and existing[end_idx] == "\n":
            end_idx += 1
        new_content = existing[:begin_idx] + drift_section + existing[end_idx:]
    else:
        # Append at end
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_content = existing + sep + "\n" + drift_section

    # Only write if content actually changed
    if _fingerprint(new_content) == _fingerprint(existing):
        return False

    target.write_text(new_content, encoding="utf-8")
    return True
