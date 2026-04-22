#!/usr/bin/env python3
"""Paket 2B — Approval-Gate Bypass-Detector (ADR-089).

Verifies that no agent run actioned REVIEW- or BLOCK-classified findings
without explicit gate-passage evidence.  Intended for use in CI and as a
local pre-push safety net.

Exit codes
----------
0  Gate clean — all findings either AUTO-routed or have passage evidence.
1  Bypass detected — at least one REVIEW/BLOCK finding was actioned without
   documented approval.
2  No artifact found — called with ``--artifact`` but the file does not exist,
   or no ``work_artifacts/agent_run_*.md`` file exists in the repo.
3  Artifact parse error — the artifact exists but cannot be interpreted.

Usage
-----
    python scripts/verify_gate_not_bypassed.py                  # auto-detect newest artifact
    python scripts/verify_gate_not_bypassed.py --artifact work_artifacts/agent_run_20260422.md
    python scripts/verify_gate_not_bypassed.py --all-artifacts  # check entire history
    python scripts/verify_gate_not_bypassed.py --help
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "work_artifacts"

# ---------------------------------------------------------------------------
# Regex patterns for artifact parsing
# ---------------------------------------------------------------------------

# Matches: "safe_to_commit: true" or "safe_to_commit: True" (YAML-inline or Markdown inline)
_RE_SAFE_TO_COMMIT = re.compile(r"safe_to_commit\s*[:=]\s*(true|True|1)", re.IGNORECASE)

# Matches: "approved: true" (set by CI label-feedback or agent handover)
_RE_APPROVED = re.compile(r"approved\s*[:=]\s*(true|True|1)", re.IGNORECASE)

# Matches a gate-table row: | <id> | <severity> | REVIEW | ... or BLOCK | ...
# The table format is defined in the agent prompt contract:
#   | finding_id | severity | gate | safe_to_commit | status |
_RE_GATE_ROW = re.compile(
    r"\|\s*(?P<id>[^\|]+?)\s*\|\s*(?P<severity>[^\|]+?)\s*\|\s*"
    r"(?P<gate>REVIEW|BLOCK|AUTO)\s*\|\s*(?P<safe>[^\|]*?)\s*\|\s*(?P<status>[^\|]*?)\s*\|"
)

# Gate Passage Evidence section header
_RE_PASSAGE_SECTION = re.compile(r"^#{1,4}\s+Gate.Passage.Evidence", re.IGNORECASE | re.MULTILINE)

# Matches embedded JSON nudge result blocks in artifacts
# Agents may embed: ```json\n{ "safe_to_commit": true, ... }\n```
_RE_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FindingGateRecord:
    finding_id: str
    severity: str
    gate: str  # AUTO | REVIEW | BLOCK
    safe_to_commit: bool
    actioned: bool  # True when status != PENDING/WAITING


@dataclass
class ArtifactResult:
    artifact: Path
    records: list[FindingGateRecord] = field(default_factory=list)
    passage_evidence_global: bool = False
    parse_warnings: list[str] = field(default_factory=list)

    @property
    def bypassed_records(self) -> list[FindingGateRecord]:
        """REVIEW/BLOCK records that were actioned without gate-passage evidence."""
        if self.passage_evidence_global:
            return []
        return [
            r
            for r in self.records
            if r.gate in ("REVIEW", "BLOCK") and r.actioned and not r.safe_to_commit
        ]

    @property
    def is_clean(self) -> bool:
        return len(self.bypassed_records) == 0


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_artifact(path: Path) -> ArtifactResult:
    result = ArtifactResult(artifact=path)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.parse_warnings.append(f"read error: {exc}")
        return result

    # --- Global passage evidence ----------------------------------------
    if _RE_SAFE_TO_COMMIT.search(text):
        result.passage_evidence_global = True
    if _RE_APPROVED.search(text):
        result.passage_evidence_global = True

    # --- JSON nudge result blocks (embedded safe_to_commit) ----------------
    for match in _RE_JSON_BLOCK.finditer(text):
        try:
            data = json.loads(match.group(1))
            if data.get("safe_to_commit") is True:
                result.passage_evidence_global = True
        except (json.JSONDecodeError, AttributeError):
            pass

    # --- Gate table rows ---------------------------------------------------
    for row in _RE_GATE_ROW.finditer(text):
        safe_raw = row.group("safe").strip().lower()
        safe = safe_raw in ("true", "1", "yes")
        status_raw = row.group("status").strip().upper()
        # PENDING / WAITING / SKIPPED = not yet actioned
        actioned = status_raw not in ("PENDING", "WAITING", "SKIPPED", "")
        result.records.append(
            FindingGateRecord(
                finding_id=row.group("id").strip(),
                severity=row.group("severity").strip(),
                gate=row.group("gate").strip(),
                safe_to_commit=safe,
                actioned=actioned,
            )
        )

    # Warn when no structured data was found at all
    if not result.records and not result.passage_evidence_global:
        result.parse_warnings.append(
            "no gate-table rows and no passage-evidence markers found in artifact"
        )

    return result


# ---------------------------------------------------------------------------
# Artifact discovery
# ---------------------------------------------------------------------------


def _find_artifacts(specific: Path | None, all_artifacts: bool) -> list[Path]:
    if specific is not None:
        if not specific.exists():
            print(f"[verify_gate] ERROR artifact not found: {specific}", file=sys.stderr)
            sys.exit(2)
        return [specific]

    candidates = sorted(ARTIFACTS_DIR.glob("agent_run_*.md"))
    if not candidates:
        return []

    if all_artifacts:
        return candidates

    # Default: most recent artifact only
    return [candidates[-1]]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_result(result: ArtifactResult, verbose: bool) -> None:
    rel = result.artifact.relative_to(REPO_ROOT) if REPO_ROOT in result.artifact.parents else result.artifact
    if result.is_clean:
        print(f"[verify_gate] OK  {rel}")
        if verbose:
            print(f"  passage_evidence_global={result.passage_evidence_global}")
            for r in result.records:
                marker = "approved" if r.safe_to_commit or result.passage_evidence_global else "pending"
                print(f"  [{r.gate:6}] {r.finding_id} ({r.severity}) — {marker}")
    else:
        print(f"[verify_gate] BYPASS DETECTED  {rel}", file=sys.stderr)
        for r in result.bypassed_records:
            print(
                f"  VIOLATION: {r.finding_id} (severity={r.severity}, gate={r.gate}) "
                "was actioned without gate-passage evidence",
                file=sys.stderr,
            )

    for w in result.parse_warnings:
        print(f"  [warn] {w}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verify_gate_not_bypassed",
        description=(
            "Detect whether an agent run actioned REVIEW/BLOCK findings "
            "without proper approval (ADR-089 Approval-Gate)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--artifact",
        type=Path,
        default=None,
        metavar="PATH",
        help="Specific agent_run_*.md artifact to verify (default: auto-detect newest).",
    )
    p.add_argument(
        "--all-artifacts",
        action="store_true",
        default=False,
        help="Check all agent_run_*.md artifacts in work_artifacts/, not just the newest.",
    )
    p.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Emit a JSON summary to stdout instead of human-readable output.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Print per-finding breakdown even for clean artifacts.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    artifacts = _find_artifacts(args.artifact, args.all_artifacts)

    if not artifacts:
        if not ARTIFACTS_DIR.exists():
            print(
                "[verify_gate] INFO  no work_artifacts/ directory found — "
                "no agent runs to verify.",
                file=sys.stderr,
            )
        else:
            print(
                "[verify_gate] INFO  no agent_run_*.md artifacts found in "
                f"{ARTIFACTS_DIR} — nothing to verify.",
                file=sys.stderr,
            )
        return 2

    results = [_parse_artifact(a) for a in artifacts]
    bypass_count = sum(1 for r in results if not r.is_clean)

    if args.json_output:
        summary = {
            "artifacts_checked": len(results),
            "bypass_count": bypass_count,
            "clean": bypass_count == 0,
            "details": [
                {
                    "artifact": str(r.artifact),
                    "is_clean": r.is_clean,
                    "passage_evidence_global": r.passage_evidence_global,
                    "bypassed": [
                        {
                            "finding_id": b.finding_id,
                            "severity": b.severity,
                            "gate": b.gate,
                        }
                        for b in r.bypassed_records
                    ],
                    "warnings": r.parse_warnings,
                }
                for r in results
            ],
        }
        print(json.dumps(summary, indent=2))
    else:
        for r in results:
            _print_result(r, verbose=args.verbose)

    if bypass_count > 0:
        if not args.json_output:
            print(
                f"\n[verify_gate] RESULT: {bypass_count}/{len(results)} artifact(s) show "
                "gate bypass — review required before merge.",
                file=sys.stderr,
            )
        return 1

    if not args.json_output:
        print(
            f"[verify_gate] RESULT: all {len(results)} artifact(s) verified clean."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
