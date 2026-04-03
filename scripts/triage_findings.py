#!/usr/bin/env python3
"""Interactive triage tool for drift findings.

Reads a *_full.json analysis export and lets you label each finding as
TP / FP / Disputed.  Results are merged into ground_truth_labels.json.

Usage:
    python scripts/triage_findings.py benchmark_results/drift_self_full.json
    python scripts/triage_findings.py benchmark_results/flask_full.json --signal avs dia
    python scripts/triage_findings.py benchmark_results/django_full.json --min-score 0.3
    python scripts/triage_findings.py benchmark_results/drift_self_full.json --unlabeled-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = REPO_ROOT / "benchmark_results" / "ground_truth_labels.json"

VALID_LABELS = {"TP", "FP", "Disputed", "skip"}

# FP taxonomy types (Schicht 3 — FP root-cause classification)
VALID_FP_TYPES = {
    "structural": "Signal fires on framework/library code pattern",
    "threshold": "Score/threshold too sensitive for this repo size",
    "scope": "Finding in tests/docs/migrations/generated code",
    "semantic": "Signal misunderstands context (decorator, type hint, etc.)",
    "co_occurrence": "Two harmless patterns together trigger signal",
}


def _load_labels() -> list[dict[str, str]]:
    if LABELS_PATH.exists():
        return json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    return []


def _save_labels(labels: list[dict[str, str]]) -> None:
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(
        json.dumps(labels, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _finding_key(repo_name: str, finding: dict) -> str:
    """Stable key matching existing ground_truth_labels convention."""
    title = finding.get("title", "unknown")
    return f"{repo_name}::{title}"


def _load_findings(path: Path) -> tuple[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    repo = data.get("repo", path.stem.removesuffix("_full"))
    return repo, data.get("findings", [])


def _ask_fp_type() -> str:
    """Prompt for FP root-cause type. Returns type string or empty."""
    print("  FP Type: [S]tructural  [T]hreshold  [C]ope  s[E]mantic  c[O]-occurrence  s[K]ip")
    while True:
        try:
            choice = input("  FP Type> ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            return ""
        mapping = {
            "S": "structural",
            "T": "threshold",
            "C": "scope",
            "E": "semantic",
            "O": "co_occurrence",
            "K": "",
        }
        if choice in mapping:
            return mapping[choice]
        print("  Invalid. Use S/T/C/E/O/K")


def triage(
    findings_path: Path,
    *,
    signal_filter: set[str] | None = None,
    min_score: float = 0.0,
    unlabeled_only: bool = False,
    batch_mode: bool = False,
) -> int:
    """Run interactive triage session. Returns number of new labels added."""
    repo_name, findings = _load_findings(findings_path)
    labels = _load_labels()
    existing_keys = {e["key"] for e in labels}

    # Filter findings
    candidates = []
    for f in findings:
        if signal_filter and f.get("signal") not in signal_filter:
            continue
        if f.get("score", 0) < min_score:
            continue
        key = _finding_key(repo_name, f)
        if unlabeled_only and key in existing_keys:
            continue
        candidates.append((key, f))

    if not candidates:
        print("No findings match the filter criteria.")
        return 0

    print(f"\n{'=' * 70}")
    print(f"Triage: {repo_name} — {len(candidates)} findings to review")
    print(f"{'=' * 70}")
    print("Labels: [T]P  [F]P  [D]isputed  [S]kip  [Q]uit\n")

    added = 0
    for i, (key, f) in enumerate(candidates, 1):
        already = key in existing_keys
        tag = " (already labeled)" if already else ""

        print(f"--- [{i}/{len(candidates)}]{tag} ---")
        print(f"  Signal:   {f.get('signal', '?')}")
        print(f"  Severity: {f.get('severity', '?')}  Score: {f.get('score', '?')}")
        print(f"  Title:    {f.get('title', '?')}")
        print(f"  File:     {f.get('file', '?')}:{f.get('start_line', '?')}")
        desc = f.get("description", "")
        if desc:
            # Truncate long descriptions
            if len(desc) > 200:
                desc = desc[:197] + "..."
            print(f"  Desc:     {desc}")
        fix = f.get("fix", "")
        if fix:
            if len(fix) > 150:
                fix = fix[:147] + "..."
            print(f"  Fix:      {fix}")

        if batch_mode:
            # In batch mode, skip interactive prompts — export unlabeled
            continue

        while True:
            try:
                choice = input("  Label> ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\n\nSession interrupted. Saving progress...")
                _save_labels(labels)
                return added

            if choice in ("T", "TP"):
                label = "TP"
            elif choice in ("F", "FP"):
                label = "FP"
            elif choice in ("D", "DISPUTED"):
                label = "Disputed"
            elif choice in ("S", "SKIP"):
                break
            elif choice in ("Q", "QUIT"):
                print(f"\nSaved {added} new labels.")
                _save_labels(labels)
                return added
            else:
                print("  Invalid. Use T/F/D/S/Q")
                continue

            # Apply label
            entry = {"key": key, "label": label, "signal": f.get("signal", "")}
            # Ask for FP type taxonomy when labeling as FP
            if label == "FP" and not batch_mode:
                fp_type = _ask_fp_type()
                if fp_type:
                    entry["fp_type"] = fp_type
                    fp_cat = input("  FP category (free text, optional): ").strip()
                    if fp_cat:
                        entry["fp_category"] = fp_cat
            if already:
                # Update existing
                for e in labels:
                    if e["key"] == key:
                        e["label"] = label
                        break
            else:
                labels.append(entry)
                existing_keys.add(key)
            added += 1
            break

    _save_labels(labels)
    print(f"\n{'=' * 70}")
    print(f"Session complete: {added} new/updated labels saved to {LABELS_PATH.name}")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive triage for drift findings",
    )
    parser.add_argument(
        "findings_json",
        type=Path,
        help="Path to *_full.json analysis export",
    )
    parser.add_argument(
        "--signal",
        nargs="+",
        help="Only triage findings from these signals (e.g. --signal avs dia)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Only triage findings with score >= this value (default: 0.0)",
    )
    parser.add_argument(
        "--unlabeled-only",
        action="store_true",
        help="Skip findings that already have a label",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Non-interactive: print findings without prompting (for review)",
    )
    args = parser.parse_args()

    if not args.findings_json.exists():
        print(f"Error: {args.findings_json} not found", file=sys.stderr)
        sys.exit(1)

    signal_filter = set(args.signal) if args.signal else None
    triage(
        args.findings_json,
        signal_filter=signal_filter,
        min_score=args.min_score,
        unlabeled_only=args.unlabeled_only,
        batch_mode=args.batch,
    )


if __name__ == "__main__":
    main()
