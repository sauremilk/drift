#!/usr/bin/env python3
# ruff: noqa: E501
#   Reason: this script embeds the verbatim prose of llms.txt as string
#   constants. Long paragraph lines (tagline, feature descriptions,
#   keyword list) MUST stay on single lines so the generated file is
#   byte-identical to the authored layout. Wrapping them would change
#   the on-disk output.
"""Deterministic generator for ``llms.txt`` (Paket 1C, ADR-092).

``llms.txt`` is the public LLM-discovery surface for drift-analyzer. It
must stay in sync with:

* ``pyproject.toml`` — application version (``Release status: vX.Y.Z``)
* ``src/drift/signal_registry.py`` — list of signals, abbreviations,
  default weights, and scoring-active vs report-only split

This generator treats ``llms.txt`` as a deterministic build artefact and
replaces the previous ad-hoc hand-editing workflow. It has two modes:

* default / ``--write``: regenerate ``llms.txt`` in-place
* ``--check``: exit 1 if the regenerated content differs from disk; prints
  a unified diff. Used by the pre-push hook and CI release step.

The prose around the signal table is stable and embedded verbatim so the
generated file is byte-identical every run on the same inputs. Per-signal
SEO-tuned names and footnotes (CWE tags, "AI hallucination indicator")
live in ``_DOC_OVERRIDES`` and stay under maintainer control.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Make `src/` importable when this script is run standalone (without an
# installed drift package). The signal_registry is the authoritative
# source for signals, so we import it rather than re-declaring data.
sys.path.insert(0, str(_REPO_ROOT / "src"))

from drift.signal_registry import SignalMeta, get_all_meta  # noqa: E402

LLMS_TXT = _REPO_ROOT / "llms.txt"
PYPROJECT = _REPO_ROOT / "pyproject.toml"


# ---------------------------------------------------------------------------
# Per-signal documentation overrides
# ---------------------------------------------------------------------------
# Registry stores canonical signal metadata; llms.txt uses SEO-tuned
# display names and security-oriented footnotes (CWE identifiers, AI
# attribution hints). Overrides stay tiny and explicit — any signal not
# listed here falls back to the registry ``signal_name``.
#
# ``doc_name``: plural/descriptive form used in llms.txt
# ``extra``:    appended inside the trailing parentheses as
#               ``(weight X.YZ, <extra>)``
# ``report_detail``: rendered after the em dash on report-only lines,
#               replacing the default description
@dataclass(frozen=True)
class _DocOverride:
    doc_name: str | None = None
    extra: str | None = None
    report_detail: str | None = None


_DOC_OVERRIDES: dict[str, _DocOverride] = {
    "architecture_violation": _DocOverride(doc_name="Architecture Violations"),
    "mutant_duplicate": _DocOverride(doc_name="Mutant Duplicates"),
    "doc_impl_drift": _DocOverride(doc_name="Doc-Implementation Drift"),
    "missing_authorization": _DocOverride(extra="CWE-862"),
    "hardcoded_secret": _DocOverride(extra="CWE-798"),
    "insecure_default": _DocOverride(extra="CWE-1188"),
    "phantom_reference": _DocOverride(extra="AI hallucination indicator"),
    "temporal_volatility": _DocOverride(
        report_detail="report-only — excluded from composite score",
    ),
    "ts_architecture": _DocOverride(
        doc_name="TypeScript Architecture",
        report_detail="TS/JS layer leaks, cycles, cross-package imports",
    ),
    "cognitive_complexity": _DocOverride(
        doc_name="Cognitive Complexity",
        report_detail="deeply nested control flow",
    ),
    "circular_import": _DocOverride(
        doc_name="Circular Import",
        report_detail="circular dependency chains",
    ),
    "dead_code_accumulation": _DocOverride(
        doc_name="Dead Code Accumulation",
        report_detail="unreferenced symbols",
    ),
    "type_safety_bypass": _DocOverride(
        doc_name="Type Safety Bypass",
        report_detail="as any / @ts-ignore / double casts",
    ),
}


# Stable ordering for the scoring-active block (highest weight first,
# then alphabetical by abbreviation for deterministic ties).
def _scoring_sort_key(meta: SignalMeta) -> tuple[float, str]:
    return (-meta.default_weight, meta.abbrev)


# Stable ordering for the report-only block (alphabetical by abbreviation).
def _report_sort_key(meta: SignalMeta) -> str:
    return meta.abbrev


# ---------------------------------------------------------------------------
# Weight formatting (strip trailing zeros without losing precision)
# ---------------------------------------------------------------------------


def _format_weight(weight: float) -> str:
    """Format a signal weight for llms.txt.

    Uses as few decimal places as needed to preserve the source value
    exactly (e.g. 0.16 → ``"0.16"``, 0.005 → ``"0.005"``, 0.0 → ``"0.0"``).
    Never emits scientific notation.
    """
    if weight == 0.0:
        return "0.0"
    text = f"{weight:.6f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


# ---------------------------------------------------------------------------
# Signal block rendering
# ---------------------------------------------------------------------------


def _scoring_line(meta: SignalMeta) -> str:
    override = _DOC_OVERRIDES.get(meta.signal_id, _DocOverride())
    name = override.doc_name or meta.signal_name
    weight = _format_weight(meta.default_weight)
    tail = (
        f"(weight {weight}, {override.extra})"
        if override.extra
        else f"(weight {weight})"
    )
    return f"- {meta.abbrev}: {name} {tail}"


def _report_line(meta: SignalMeta) -> str:
    override = _DOC_OVERRIDES.get(meta.signal_id, _DocOverride())
    name = override.doc_name or meta.signal_name
    weight = _format_weight(meta.default_weight)
    detail = override.report_detail or meta.description.rstrip(".")
    # Temporal volatility keeps the legacy "(weight 0.0, ...)" form so
    # downstream LLM consumers see the explicit weight even on the first
    # report-only line.
    if meta.signal_id == "temporal_volatility":
        return f"- {meta.abbrev}: {name} (weight {weight}, {detail})"
    return f"- {meta.abbrev}: {name} — {detail}"


def _render_signals_section() -> str:
    active: list[SignalMeta] = []
    report: list[SignalMeta] = []
    for meta in get_all_meta():
        if not meta.is_core:
            continue  # Plugin signals never leak into llms.txt
        if meta.default_weight > 0.0:
            active.append(meta)
        else:
            report.append(meta)

    active.sort(key=_scoring_sort_key)
    report.sort(key=_report_sort_key)

    lines: list[str] = ["## Signals", ""]
    lines.append(
        f"### Scoring-active ({len(active)}, contribute to composite drift score)"
    )
    lines.extend(_scoring_line(m) for m in active)
    lines.append("")
    lines.append(
        f"### Report-only ({len(report)}, weight 0.0, "
        "findings shown but not scored)"
    )
    lines.extend(_report_line(m) for m in report)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prose sections (stable; no external inputs)
# ---------------------------------------------------------------------------

_HEADER = """\
# drift-analyzer

> Catches what AI coding tools break silently — structural erosion across files that passes all your tests. Drift is a quality control layer for AI-generated Python code: pattern fragmentation, architecture violations, mutant duplicates, and 21 more structural signals. No LLM in the detection pipeline.

Release status: v{version}

Package: drift-analyzer
Install: pip install -q drift-analyzer  (add -q for quiet output, hiding verbose dependency chains)
Repository: https://github.com/mick-gsk/drift
Documentation: https://mick-gsk.github.io/drift/
Command: drift analyze --repo .

## Two Modes — Same Engine

Drift runs as CLI or MCP server. Both use the same analysis engine and signal set.

CLI mode (terminals, CI):
  drift brief --task "refactor auth" → structural guardrails for agent prompts
  drift nudge --changed-files src/auth.py → real-time safe_to_commit check
  drift check --fail-on high → CI gate (exits 1 on violations)
  drift analyze --repo . --format json → full analysis report

MCP mode (Cursor, Claude Code, Copilot):
  drift_brief → scope-aware guardrails injected into agent context
  drift_nudge → safe_to_commit: true/false after each edit
  drift_diff → before/after comparison before push
  drift_feedback → mark findings as TP/FP to calibrate signal weights
  drift_retrieve → BM25 search over drift's own verified fact sources (POLICY, ADRs, audits, signal rationale, benchmark evidence) with stable fact_ids
  drift_cite → expand a fact_id to its verbatim chunk with sha256 anchor for grounded agent citations

## Fact-Grounding Contract (ADR-091)

Agents making claims about drift itself (policy, signals, ADR decisions, audit artefacts, benchmark evidence) MUST call drift_retrieve first and cite at least one fact_id. See .github/instructions/drift-rag-grounding.instructions.md. Retrieval is deterministic (lexical BM25, no LLM, no embeddings in MVP); the corpus_sha256 in every response anchors reproducibility.

## safe_to_commit

drift nudge returns a safe_to_commit boolean with blocking reasons. Blocks on:
- New critical/high-severity findings
- Score degradation exceeding threshold
- Expired baseline (full rescan needed)
- Parse failures in changed files
- Git change detection failure

This gives AI coding agents an immediate go/no-go signal after each edit — no manual review needed.

## Use Cases

- Detect pattern fragmentation: same concern implemented N different ways in one module
- Find architecture violations: imports crossing layer boundaries, circular dependencies
- Identify mutant duplicates: near-identical functions from copy-paste AI scaffolding
- Measure explainability deficit: complex functions without documentation or types
- Track temporal volatility: files changed by too many authors too fast
- Detect system misalignment: novel import patterns foreign to their module
- Detect phantom references: unresolvable function/class references (AI hallucination indicator)
- CI gate: block PRs on high-severity architectural findings via GitHub Actions
- Agent guardrails: inject structural constraints before AI coding sessions
- Trend tracking: monitor drift score evolution over time

## Benchmarks

Ground-truth precision: 100% (47 TP, 0 FP across 114 fixtures, 17 signals)
Ground-truth recall: 100% (0 FN)
Mutation recall: 100% (25/25 injected patterns detected)
Wild-repo precision: 77% strict / 95% lenient (5 repos, historical v0.5 model)
No LLM in the detection pipeline — same input, same output, reproducible in CI.

Artifacts: benchmark_results/v2.7.0_precision_recall_baseline.json, benchmark_results/mutation_benchmark.json
Full study: docs/STUDY.md
"""

_FOOTER = """\
## Docs

- [Documentation](https://mick-gsk.github.io/drift/)
- [Quick Start](https://mick-gsk.github.io/drift/getting-started/quickstart/)
- [Signal Reference](https://mick-gsk.github.io/drift/algorithms/signals/)
- [Scoring Model](https://mick-gsk.github.io/drift/algorithms/scoring/)
- [FAQ](https://mick-gsk.github.io/drift/faq/)
- [Trust & Evidence](https://mick-gsk.github.io/drift/trust-evidence/)

## Optional

- [Full Benchmark Study](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md): 100% ground-truth precision/recall on 114 fixtures (v2.7.0+), 77% strict wild-repo precision (v0.5 model on 5 repos)
- [Changelog](https://github.com/mick-gsk/drift/blob/main/CHANGELOG.md): version history and signal improvements
- [Case Studies](https://mick-gsk.github.io/drift/case-studies/): FastAPI, Pydantic, Django, Paramiko
- [GitHub Action](https://github.com/mick-gsk/drift/blob/main/action.yml): CI integration with SARIF upload

## Keywords

architectural drift detection, architecture erosion analysis, cross-file coherence detection, structural code quality, architectural linter, architecture degradation, technical debt detection, dependency cycle detection, import analysis, pattern fragmentation, static analysis, Python, monorepo, GitHub Copilot, AI coding tools, architecture enforcement
"""


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _read_pyproject_version() -> str:
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    version = data["project"]["version"]
    # Reject non-semver-looking strings early so a corrupted pyproject.toml
    # does not silently poison llms.txt.
    if not re.match(r"^\d+\.\d+\.\d+", version):
        raise SystemExit(
            f"generate_llms_txt: invalid version in pyproject.toml: {version!r}"
        )
    return version


def render_llms_txt() -> str:
    """Render the full llms.txt content deterministically.

    Returns a string with a single trailing newline. All prose sections
    are embedded verbatim; only the version line and the signal table
    are derived from external inputs.
    """
    version = _read_pyproject_version()
    signals_section = _render_signals_section()
    parts = [
        _HEADER.format(version=version),
        signals_section,
        "",  # blank line between signals block and Docs heading
        "",  # matches existing double blank-line style
        _FOOTER,
    ]
    content = "\n".join(parts)
    # Collapse accidental triple blank lines and ensure a single trailing
    # newline. _HEADER already ends with "\n"; join with "\n" adds one
    # more, so we normalise here.
    content = re.sub(r"\n{3,}", "\n\n", content)
    if not content.endswith("\n"):
        content += "\n"
    return content


def _diff(expected: str, actual: str) -> str:
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile="llms.txt (on disk)",
            tofile="llms.txt (generated)",
            n=3,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify llms.txt from authoritative sources.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the on-disk llms.txt does not match the generated one.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write the generated llms.txt (default action).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(LLMS_TXT),
        help="Output path (default: llms.txt at repo root).",
    )
    args = parser.parse_args(argv)

    expected = render_llms_txt()
    target = Path(args.output)

    if args.check:
        if not target.exists():
            print(
                f"FAIL: {target} does not exist. "
                f"Run `python scripts/generate_llms_txt.py --write`.",
                file=sys.stderr,
            )
            return 1
        actual = target.read_text(encoding="utf-8")
        if actual != expected:
            print(f"FAIL: {target} is out of date.", file=sys.stderr)
            print(_diff(expected, actual), file=sys.stderr)
            print(
                "Fix: `python scripts/generate_llms_txt.py --write`",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {target} is up to date.")
        return 0

    # Default = write (also covered explicitly by --write)
    target.write_text(expected, encoding="utf-8")
    print(
        f"Wrote {target} "
        f"(version={_read_pyproject_version()}, "
        f"signals={sum(1 for m in get_all_meta() if m.is_core)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
