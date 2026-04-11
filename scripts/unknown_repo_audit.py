#!/usr/bin/env python3
"""Unknown-repo precision audit: run drift on a never-seen-before repo.

Generates a human-reviewable audit sheet (JSON + Markdown) where each
HIGH/CRITICAL finding can be annotated as TP / FP / UNCERTAIN.

This measures real-world precision — the gap between benchmark precision
(97.3%) and what a skeptical developer actually experiences.

Usage:
    # Audit a local repo:
    python scripts/unknown_repo_audit.py /path/to/unknown-repo

    # Audit with shallow clone from URL:
    python scripts/unknown_repo_audit.py https://github.com/org/repo.git

    # Re-evaluate a previously annotated audit:
    python scripts/unknown_repo_audit.py --evaluate audit_results/my_repo.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure src/ is on the path when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from drift.analyzer import analyze_repo
from drift.config import DriftConfig
from drift.models import Severity


def _shallow_clone(url: str, dest: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    return dest


def _run_audit(repo_path: Path, label: str) -> dict:
    """Analyze a repo and produce an audit-ready data structure."""
    config = DriftConfig(
        include=["**/*.py"],
        exclude=[
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.venv*/**",
            "**/docs/**",
            "**/docs_src/**",
            "**/examples/**",
            "**/tests/**",
            "**/test_*",
        ],
        embeddings_enabled=False,
    )

    analysis = analyze_repo(repo_path, config=config, since_days=365)

    # Build audit entries — focus on HIGH + CRITICAL (where FP damage is worst)
    audit_entries = []
    reviewable = [
        f
        for f in analysis.findings
        if f.severity in (Severity.HIGH, Severity.CRITICAL, Severity.MEDIUM)
    ]
    # Sort by impact descending so worst findings come first
    reviewable.sort(key=lambda f: -f.impact)

    for i, finding in enumerate(reviewable):
        audit_entries.append(
            {
                "id": i + 1,
                "signal": finding.signal_type,
                "severity": finding.severity.value,
                "score": round(finding.score, 3),
                "impact": round(finding.impact, 3),
                "title": finding.title,
                "description": finding.description,
                "file": str(finding.file_path) if finding.file_path else None,
                "line": finding.start_line,
                "fix": finding.fix,
                "related_files": [str(p) for p in finding.related_files[:5]],
                # Human annotation fields — to be filled during review
                "verdict": None,  # "tp", "fp", "uncertain"
                "reviewer_note": None,
            }
        )

    return {
        "meta": {
            "repo": label,
            "analyzed_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "drift_score": round(analysis.drift_score, 3),
            "severity": analysis.severity.value,
            "total_files": analysis.total_files,
            "total_functions": analysis.total_functions,
            "total_findings": len(analysis.findings),
            "reviewable_findings": len(audit_entries),
            "duration_s": round(analysis.analysis_duration_seconds, 2),
        },
        "findings": audit_entries,
    }


def _write_markdown(audit: dict, md_path: Path) -> None:
    """Write a human-friendly markdown review sheet."""
    meta = audit["meta"]
    lines = [
        f"# Drift Precision Audit: {meta['repo']}",
        "",
        f"- **Score:** {meta['drift_score']} ({meta['severity']})",
        f"- **Files:** {meta['total_files']} | Functions: {meta['total_functions']}",
        f"- **Findings:** {meta['total_findings']} total, "
        f"{meta['reviewable_findings']} reviewable (MEDIUM+)",
        f"- **Duration:** {meta['duration_s']}s",
        f"- **Analyzed:** {meta['analyzed_at']}",
        "",
        "## Review Instructions",
        "",
        "For each finding, mark the **Verdict** column:",
        "- **TP** — Real problem. You'd want this flagged in a code review.",
        "- **FP** — Not a real problem. This would erode trust if shown to a dev.",
        "- **?** — Unsure / context-dependent.",
        "",
        "## Findings",
        "",
        "| # | Signal | Sev | Score | File | Title | Verdict |",
        "|---|--------|-----|-------|------|-------|---------|",
    ]

    for f in audit["findings"]:
        file_str = f["file"] or "—"
        # Truncate long paths for table readability
        if len(file_str) > 40:
            file_str = "…" + file_str[-37:]
        title = f["title"][:60]
        lines.append(
            f"| {f['id']} | {f['signal']} | {f['severity']} | "
            f"{f['score']} | {file_str} | {title} | |"
        )

    lines.extend(
        [
            "",
            "## Detailed Findings",
            "",
        ]
    )

    for f in audit["findings"]:
        lines.append(f"### #{f['id']}: {f['title']}")
        lines.append(f"**Signal:** {f['signal']} | **Severity:** {f['severity']} "
                      f"| **Score:** {f['score']} | **Impact:** {f['impact']}")
        lines.append(f"**File:** {f['file'] or '—'}"
                      + (f" (line {f['line']})" if f['line'] else ""))
        lines.append("")
        lines.append(f"> {f['description']}")
        lines.append("")
        if f["fix"]:
            lines.append(f"**Fix:** {f['fix']}")
            lines.append("")
        if f["related_files"]:
            lines.append("**Related:** " + ", ".join(f["related_files"]))
            lines.append("")
        lines.append("**Verdict:** TP / FP / ?")
        lines.append("**Note:**")
        lines.append("")
        lines.append("---")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def _evaluate(audit_path: Path) -> None:
    """Evaluate a previously annotated audit JSON."""
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    meta = audit["meta"]

    total = 0
    tp = 0
    fp = 0
    uncertain = 0
    unannotated = 0

    by_signal: dict[str, dict[str, int]] = {}

    for f in audit["findings"]:
        total += 1
        signal = f["signal"]
        if signal not in by_signal:
            by_signal[signal] = {"tp": 0, "fp": 0, "uncertain": 0}

        verdict = (f.get("verdict") or "").strip().lower()
        if verdict == "tp":
            tp += 1
            by_signal[signal]["tp"] += 1
        elif verdict == "fp":
            fp += 1
            by_signal[signal]["fp"] += 1
        elif verdict in ("uncertain", "?"):
            uncertain += 1
            by_signal[signal]["uncertain"] += 1
        else:
            unannotated += 1

    annotated = tp + fp + uncertain
    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")

    print(f"\n{'=' * 60}")
    print(f"Precision Audit Evaluation: {meta['repo']}")
    print(f"{'=' * 60}")
    print(f"  Drift Score:     {meta['drift_score']}")
    print(f"  Total Findings:  {total}")
    print(f"  Annotated:       {annotated} ({unannotated} remaining)")
    print(f"  TP:              {tp}")
    print(f"  FP:              {fp}")
    print(f"  Uncertain:       {uncertain}")
    print(f"  REAL PRECISION:  {precision:.1%}" if annotated > 0 else "  (no annotations)")
    print()

    if by_signal:
        print("  Per-signal breakdown:")
        for sig, counts in sorted(by_signal.items()):
            s_total = counts["tp"] + counts["fp"]
            s_prec = counts["tp"] / s_total if s_total > 0 else float("nan")
            print(f"    {sig:<30s}  TP={counts['tp']}  FP={counts['fp']}  "
                  f"?={counts['uncertain']}  P={s_prec:.0%}")

    if precision < 0.9 and annotated >= 10:
        print(f"\n  ⚠ Real-world precision {precision:.1%} is below 90% target.")
        print("    This is the gap between benchmark precision and customer experience.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a precision audit on a previously-unseen repo."
    )
    parser.add_argument(
        "target",
        help="Local repo path, git URL to shallow-clone, or --evaluate JSON path.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate a previously annotated audit JSON instead of running analysis.",
    )
    parser.add_argument(
        "--output-dir",
        default="audit_results",
        help="Directory for output files (default: audit_results/).",
    )
    args = parser.parse_args()

    if args.evaluate:
        _evaluate(Path(args.target))
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target = args.target
    is_url = target.startswith("http://") or target.startswith("https://")

    if is_url:
        # Extract repo name from URL
        label = target.rstrip("/").split("/")[-1].replace(".git", "")
        with tempfile.TemporaryDirectory() as tmp:
            clone_dir = Path(tmp) / label
            print(f"Cloning {target} ...")
            _shallow_clone(target, clone_dir)
            audit = _run_audit(clone_dir, label)
    else:
        repo_path = Path(target).resolve()
        if not repo_path.is_dir():
            print(f"Error: {target} is not a directory", file=sys.stderr)
            sys.exit(1)
        label = repo_path.name
        audit = _run_audit(repo_path, label)

    # Write outputs
    json_path = output_dir / f"{label}_audit.json"
    md_path = output_dir / f"{label}_audit.md"

    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(audit, md_path)

    print(f"\nAudit complete for '{label}':")
    print(f"  Score:    {audit['meta']['drift_score']} ({audit['meta']['severity']})")
    print(f"  Findings: {audit['meta']['reviewable_findings']} reviewable")
    print(f"  JSON:     {json_path}")
    print(f"  Markdown: {md_path}")
    print("\nNext steps:")
    print(f"  1. Open {md_path} and annotate each finding as TP/FP/?")
    print(f"  2. Transfer verdicts to {json_path} (set 'verdict' field)")
    print(f"  3. Run: python scripts/unknown_repo_audit.py --evaluate {json_path}")


if __name__ == "__main__":
    main()
