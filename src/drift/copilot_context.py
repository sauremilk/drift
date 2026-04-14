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
from typing import TYPE_CHECKING

from drift.api_helpers import build_drift_score_scope, signal_abbrev
from drift.finding_context import (
    classify_path_context,
    is_non_operational_context,
    split_findings_by_context,
)
from drift.models import Finding, RepoAnalysis, SignalType

if TYPE_CHECKING:
    from drift.config import DriftConfig

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


def _resolve_config(config: DriftConfig | None = None) -> DriftConfig:
    """Return the provided config or a default DriftConfig instance."""
    if config is not None and hasattr(config, "finding_context"):
        return config

    from drift.config import DriftConfig

    return DriftConfig()


def _operational_findings(
    findings: list[Finding],
    *,
    config: DriftConfig | None = None,
) -> list[Finding]:
    """Return findings prioritized for agent-facing context outputs."""
    cfg = _resolve_config(config)
    prioritized, _excluded, _counts = split_findings_by_context(
        findings,
        cfg,
        include_non_operational=False,
    )
    return prioritized


def _select_hotspot_module(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
):
    """Prefer the most eroded operational module for guidance footers."""
    if not analysis.module_scores:
        return None

    cfg = _resolve_config(config)
    operational_modules = [
        module
        for module in analysis.module_scores
        if not is_non_operational_context(classify_path_context(module.path, cfg), cfg)
    ]
    candidates = operational_modules or analysis.module_scores
    return max(candidates, key=lambda m: m.drift_score)


def _collect_actionable_findings(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> dict[SignalType, list[Finding]]:
    """Collect actionable findings that qualify for Copilot guidance."""
    actionable: dict[SignalType, list[Finding]] = {}
    for finding in _operational_findings(analysis.findings, config=config):
        try:
            signal = SignalType(finding.signal_type)
        except ValueError:
            continue
        if signal in _ACTIONABLE_SIGNALS and finding.score >= _MIN_SCORE:
            actionable.setdefault(signal, []).append(finding)

    return {
        signal: findings
        for signal, findings in actionable.items()
        if len(findings) >= _MIN_FINDING_COUNT
    }


def _scope_for_finding(finding: Finding) -> str:
    """Return a stable scope value for machine-readable constraints."""
    if finding.file_path is None:
        return "repo"

    file_path = finding.file_path.as_posix()
    parent = finding.file_path.parent.as_posix()
    if parent in {"", "."}:
        return file_path
    return parent


def generate_constraints_payload(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> dict[str, object]:
    """Generate a machine-readable constraints payload for agent workflows."""
    actionable = _collect_actionable_findings(analysis, config=config)
    constraints: list[dict[str, object]] = []

    for signal in sorted(actionable, key=lambda s: len(actionable[s]), reverse=True):
        ordered_findings = sorted(
            actionable[signal],
            key=lambda finding: (
                -finding.score,
                finding.file_path.as_posix() if finding.file_path else "",
                finding.start_line or 0,
                finding.title,
            ),
        )
        for finding in ordered_findings:
            constraint_text = finding.fix or finding.description or finding.title
            constraints.append(
                {
                    "signal": signal_abbrev(signal),
                    "signal_type": signal.value,
                    "severity": finding.severity.value,
                    "scope": _scope_for_finding(finding),
                    "constraint": constraint_text,
                    "rule_id": finding.rule_id,
                    "file": finding.file_path.as_posix() if finding.file_path else None,
                    "start_line": finding.start_line,
                }
            )

    payload: dict[str, object] = {
        "constraints": constraints,
        "summary": {
            "drift_score": round(analysis.drift_score, 3),
            "drift_score_scope": build_drift_score_scope(context="repo"),
            "severity": analysis.severity.value,
            "constraint_count": len(constraints),
        },
    }
    if analysis.trend is not None:
        payload["trend"] = {
            "direction": analysis.trend.direction,
            "delta": analysis.trend.delta,
            "history_depth": analysis.trend.history_depth,
        }
    return payload


def generate_instructions(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> str:
    """Generate a Markdown section with Copilot instructions from analysis results.

    Only actionable signals with sufficient severity/frequency are included.
    """
    actionable = _collect_actionable_findings(analysis, config=config)

    if not actionable:
        return _wrap_markers(
            "## Architectural Constraints (drift-generated)\n\n"
            "No significant architectural issues detected. Drift score: "
            f"{analysis.drift_score:.3f} ({analysis.severity.value}).\n"
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
    sections.append(f"- **Drift Score**: {analysis.drift_score:.3f} ({analysis.severity.value})")
    if analysis.trend:
        direction = analysis.trend.direction
        delta = analysis.trend.delta
        sections.append(f"- **Trend**: {direction}" + (f" (delta {delta:+.2f})" if delta else ""))
    worst = _select_hotspot_module(analysis, config=config)
    if worst is not None:
        sections.append(
            f"- **Most eroded module**: `{worst.path.as_posix()}` "
            f"(score: {worst.drift_score:.3f})"
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
# Multi-format generators (Cursor, Claude)
# ---------------------------------------------------------------------------

#: Valid target identifiers for ``--target``
VALID_TARGETS: frozenset[str] = frozenset(
    {"copilot", "cursor", "claude", "windsurf", "agents"}
)


def generate_cursorrules(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> str:
    """Generate ``.cursorrules`` content from analysis results.

    Cursor uses a flat rule-per-line format inside a ``.cursorrules``
    file at the repository root.
    """
    actionable = _collect_actionable_findings(analysis, config=config)

    lines: list[str] = []
    lines.append("# Architectural constraints (drift-generated)")
    lines.append(
        f"# Drift score: {analysis.drift_score:.3f} ({analysis.severity.value})"
    )
    lines.append("")

    if not actionable:
        lines.append("# No significant architectural issues detected.")
        return "\n".join(lines) + "\n"

    for signal in sorted(actionable, key=lambda s: len(actionable[s]), reverse=True):
        findings = actionable[signal]
        abbr = signal_abbrev(signal)
        for f in findings[:5]:
            rule_text = f.fix or f.description or f.title
            # Cursor rules are single-line directives
            lines.append(f"# [{abbr}] {rule_text}")

    lines.append("")
    return "\n".join(lines) + "\n"


def generate_claude_instructions(
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> str:
    """Generate ``CLAUDE.md`` content from analysis results.

    Claude Code uses a ``CLAUDE.md`` file at the repository root.
    Format uses Markdown with a clear instruction section.
    """
    actionable = _collect_actionable_findings(analysis, config=config)

    sections: list[str] = []
    sections.append("# Architectural Constraints (drift-generated)\n")
    sections.append(
        f"Drift score: {analysis.drift_score:.3f} ({analysis.severity.value})\n"
    )

    if not actionable:
        sections.append("No significant architectural issues detected.\n")
        return "\n".join(sections)

    sections.append("## Rules\n")
    for signal in sorted(actionable, key=lambda s: len(actionable[s]), reverse=True):
        findings = actionable[signal]
        abbr = signal_abbrev(signal)
        for f in findings[:5]:
            rule_text = f.fix or f.description or f.title
            sections.append(f"- **{abbr}**: {rule_text}")

    worst = _select_hotspot_module(analysis, config=config)
    if worst is not None:
        sections.append("")
        sections.append("## Hotspots\n")
        sections.append(
            f"- Most eroded module: `{worst.path.as_posix()}` "
            f"(score: {worst.drift_score:.3f})"
        )

    sections.append("")
    return "\n".join(sections) + "\n"


def target_default_path(target: str, repo_path: Path) -> Path:
    """Return the default output path for a given target format."""
    if target == "cursor":
        return repo_path / ".cursorrules"
    if target == "windsurf":
        return repo_path / ".windsurfrules"
    if target == "claude":
        return repo_path / "CLAUDE.md"
    if target == "agents":
        return repo_path / "AGENTS.md"
    # copilot (default)
    return repo_path / ".github" / "copilot-instructions.md"


def generate_for_target(
    target: str,
    analysis: RepoAnalysis,
    *,
    config: DriftConfig | None = None,
) -> str:
    """Generate instructions for the specified target format."""
    if target == "cursor":
        return generate_cursorrules(analysis, config=config)
    if target == "windsurf":
        return generate_cursorrules(analysis, config=config)
    if target == "claude":
        return generate_claude_instructions(analysis, config=config)
    if target == "agents":
        return generate_claude_instructions(analysis, config=config)
    return generate_instructions(analysis, config=config)


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
