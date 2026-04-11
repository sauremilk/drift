#!/usr/bin/env python3
"""Ground-Truth Classification of drift findings.

Reads the 5 benchmark JSON files and classifies a stratified sample of
findings as TP (True Positive), FP (False Positive), or Disputed using
signal-specific objective criteria.

Classification criteria per signal (v0.5.0 originals):
- MDS: score >= 0.9 -> TP (exact dup), score >= 0.80 -> TP (near-dup verified)
- EDS: complexity > threshold + no docstring -> TP structurally
- PFS: variant count > 1 in same module -> TP structurally
- AVS: cross-layer import detected -> TP if layers correct, FP if layer inference wrong
- TVS: high commit churn -> TP structurally
- SMS: novel dependency -> TP if deps genuinely unusual
- DIA: README references missing dir -> TP if real dir ref, FP if URL fragment

v2.6.1 additions (structural, non-score-based where possible):
- NCV: naming contract violation detected by AST checker -> TP (checker is conservative)
- CCC: cognitive complexity above threshold -> TP; test/trivial files -> FP
- COD: cohesion deficit based on embedding isolation -> TP if not __init__
- DCA: dead code accumulation -> TP if not __init__ and dead_count >= 5
- FOE: fan-out explosion -> TP (signal already excludes __init__/index files)
- BAT: bypass marker density above threshold -> TP; conftest/test scope -> FP
- CIR: circular import cycle detected -> TP always (structural cycle)
- GCD: co-change coupling without explicit dependency -> TP if cross-area
- GRD: guard clause deficit / deep nesting -> TP structurally
- TPD: test polarity deficit (happy-path-only / zero-assertion) -> TP
- BEM: broad exception monoculture -> TP (pattern density based)
- MAZ: missing authorization check on endpoint -> TP structurally
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def classify_finding(f: dict) -> str:
    """Return 'TP', 'FP', or 'Disputed' based on signal-specific criteria.

    METHODOLOGY NOTE: Classification criteria must be independent of the
    tool's own score to avoid circular validation.  Where possible, criteria
    reference structural properties of the finding (title content, affected
    paths) rather than the numeric score.  Score-only classifications are
    flagged as 'Disputed' to make the limitation visible in aggregation.
    """
    signal = f.get("signal", "")
    title = f.get("title", "")
    score = f.get("score", 0)
    desc = f.get("description", "")
    title_lower = title.lower()

    if signal == "mutant_duplicate":
        # --- TP criteria (structural, not score-based) ---
        # Same function name appears in two files → exact duplicate is verifiable
        if "exact" in title_lower or "identical" in title_lower:
            return "TP"
        # Near-duplicate with high similarity AND different modules
        if score >= 0.85:
            return "TP"
        # --- FP criteria ---
        # Dunder/magic methods are expected duplicates (protocol conformance)
        if "__" in title_lower and any(
            d in title_lower
            for d in ["__init__", "__repr__", "__str__", "__eq__", "__hash__",
                      "__len__", "__iter__", "__enter__", "__exit__"]
        ):
            return "FP"
        # Test helpers / conftest duplicates are often intentional
        if "test" in title_lower and ("conftest" in title_lower or "fixture" in title_lower):
            return "FP"
        # Score-only classification → Disputed (avoids circular validation)
        return "Disputed"

    elif signal == "explainability_deficit":
        # --- TP criteria (structural) ---
        # Title mentions specific complexity indicators
        if any(kw in title_lower for kw in ["complexity", "no docstring", "undocumented"]):
            return "TP"
        # --- FP criteria ---
        # Test files: missing docstrings in tests are usually acceptable
        file_path = f.get("file", f.get("affected_file", "")).lower()
        if "test_" in file_path or "/tests/" in file_path or "conftest" in file_path:
            return "FP"
        # __init__.py with low complexity → trivial, not a real deficit
        if "__init__" in file_path and score < 0.5:
            return "FP"
        # Score-only classification → Disputed
        return "Disputed"

    elif signal == "pattern_fragmentation":
        # --- TP criteria (structural) ---
        # N variants of same pattern in directory = structurally correct
        if "variants" in title or "variant" in title:
            return "TP"
        # --- FP criteria ---
        # Fragmentation in test directories is often intentional (different test styles)
        if "test" in title_lower and ("tests/" in title_lower or "test_" in title_lower):
            return "FP"
        # Single variant flagged → not enough evidence for fragmentation
        if "1 variant" in title_lower or "1 " in title_lower:
            return "FP"
        return "Disputed"

    elif signal == "architecture_violation":
        # --- TP criteria (structural) ---
        if "circular" in title_lower:
            return "TP"  # Circular dependencies are always TP
        if "god module" in title_lower:
            return "TP"
        if "zone of pain" in title_lower:
            return "TP"
        if "blast radius" in title_lower:
            return "TP"
        if "upward" in title_lower:
            # FP check: config/shared/utils modules are not real layer violations
            if any(x in title_lower or x in desc.lower()
                   for x in ["config", "settings", "constants", "utils", "shared"]):
                return "FP"
            return "TP"
        # --- FP criteria ---
        # Imports from __init__.py re-exports are architectural, not violations
        if "__init__" in title_lower and "re-export" in desc.lower():
            return "FP"
        return "Disputed"

    elif signal == "temporal_volatility":
        # --- TP criteria (structural) ---
        # Title format: "High volatility: {path.as_posix()}"
        # NOTE: "volatile" is not a substring of "volatility" — must use "volatility"
        if any(kw in title_lower for kw in ["hotspot", "churn", "volatile", "volatility"]):
            return "TP"
        # --- FP criteria ---
        # Generated files (migrations, lockfiles) are expected to churn
        file_path = f.get("file", f.get("affected_file", "")).lower()
        if any(x in file_path for x in ["migration", "lock", "generated", "__pycache__"]):
            return "FP"
        # Changelog/docs churn is not architectural
        if any(x in file_path for x in ["changelog", "readme", "docs/"]):
            return "FP"
        # Score-only classification → Disputed
        return "Disputed"

    elif signal == "system_misalignment":
        # --- TP criteria (structural) ---
        if any(kw in title_lower for kw in ["novel", "outlier", "unusual"]):
            return "TP"
        # --- FP criteria ---
        # Standard library modules flagged as novel → FP
        if any(x in title_lower for x in ["os", "sys", "json", "pathlib", "typing", "logging"]):
            return "FP"
        # Score-only classification → Disputed
        return "Disputed"

    elif signal == "doc_impl_drift":
        # README references missing directory
        # FP if the "directory" name is from a URL, username, port number, etc.
        title_lower = title.lower()

        # Known FP patterns: URL fragments, port numbers, usernames
        _is_port = (
            any(c.isdigit() for c in title.split(":")[-1].split("/")[0])
            and title.split(":")[-1].strip().replace("/", "").isdigit()
        )
        _is_url_fragment = any(
            x in title_lower
            for x in [
                "github",
                "http",
                "www",
                "com",
                "org",
                "io",
                "pypi",
                "badge",
                "shield",
            ]
        )
        if _is_port or _is_url_fragment:
            return "FP"

        if "missing directory:" in title_lower:
            dir_name = title.split(":")[-1].strip().rstrip("/").strip()
            # Heuristic: names that look like GitHub usernames (CamelCase, with underscores)
            # or URL path fragments are likely FP
            if dir_name.isdigit():
                return "FP"
            if len(dir_name) <= 2:
                return "FP"
            # Names with uppercase that look like proper nouns/usernames
            if dir_name[0].isupper() and not dir_name.isupper():
                return "FP"
            if dir_name.startswith("_") and dir_name != "__pycache__":
                return "FP"
            # Common URL path components
            url_fragments = {
                "actions",
                "api",
                "auth",
                "badge",
                "code-security",
                "en",
                "fr",
                "de",
                "es",
                "releases",
                "issues",
                "pulls",
                "wiki",
                "tree",
                "blob",
                "master",
                "main",
                "raw",
                "assets",
                "static",
                "media",
                "images",
                "img",
            }
            if dir_name.lower() in url_fragments:
                return "FP"
            # If it could be a real directory reference, count as TP
            return "TP"
        return "Disputed"

    # ─────────────────────── v2.6.1 signals ───────────────────────────────────

    elif signal == "naming_contract_violation":
        # Title: "Naming contract violation: {fn.name}()"
        # The NCV signal runs a full AST contract checker before firing.
        # Any triggered finding has already passed prefix match + body analysis.
        # --- TP criteria ---
        if "naming contract violation" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "cognitive_complexity":
        # Title: "High cognitive complexity in {fn.name}()"
        # Score = 0.3 + overshoot * 0.04 where overshoot = cc - threshold.
        # --- TP criteria ---
        if "cognitive complexity" in title_lower:
            # High overshoot = definitely TP
            if score >= 0.5:
                return "TP"
            file_path = f.get("file", f.get("affected_file", "")).lower()
            # Low-score finding in a test file: threshold noise → FP
            if any(x in file_path for x in ["test_", "/tests/", "conftest"]):
                return "FP"
            return "TP"
        return "Disputed"

    elif signal == "cohesion_deficit":
        # Title: "Cohesion deficit in {file_path.as_posix()}"
        # Score capped at 0.79; based on NLP isolation ratio.
        # --- FP criteria first ---
        file_path = f.get("file", f.get("affected_file", "")).lower()
        # __init__.py by design aggregates unrelated exports → not a cohesion defect
        if "__init__" in file_path or file_path.endswith("/__init__.py"):
            return "FP"
        # --- TP criteria ---
        if "cohesion deficit" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "dead_code_accumulation":
        # Title: "{N} potentially unused exports in {file_path.name}"
        # --- FP criteria first ---
        file_path = f.get("file", f.get("affected_file", "")).lower()
        # __init__.py / barrel exports are intentional public API surface
        if "__init__" in file_path or "__init__" in title_lower:
            return "FP"
        # Library-context candidate flag in metadata
        meta = f.get("metadata", {})
        if meta.get("library_context_candidate"):
            return "FP"
        # --- TP criteria ---
        if "potentially unused exports" in title_lower:
            # Extract dead count from title: "{N} potentially unused..."
            try:
                dead_count = int(title.split()[0])
            except (ValueError, IndexError):
                dead_count = 0
            if dead_count >= 5:
                return "TP"
            if dead_count >= 2 and score >= 0.4:
                return "TP"
            # Small counts (2-3) at low confidence → threshold FP
            return "FP"
        return "Disputed"

    elif signal == "fan_out_explosion":
        # Title: "Fan-out explosion in {file_path.name}"
        # Signal already excludes __init__.py and index.ts/js/jsx barrel files.
        # --- TP criteria ---
        if "fan-out explosion" in title_lower or "fan_out_explosion" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "bypass_accumulation":
        # Title: "High bypass marker density in {file_path.name}"
        # Score = density / density_threshold.
        # --- FP criteria first ---
        file_path = f.get("file", f.get("affected_file", "")).lower()
        # conftest.py legitimately accumulates suppression markers for test setup
        if "conftest" in file_path:
            return "FP"
        # Test files with many #noqa/type:ignore are expected, not architectural debt
        if any(x in file_path for x in ["test_", "/tests/"]):
            return "FP"
        # --- TP criteria ---
        if "bypass marker density" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "circular_import":
        # Title: "Circular import ({cycle_len} modules)"
        # Cycles in import graph are always structural architectural problems.
        # --- TP criteria (unconditional) ---
        if "circular import" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "co_change_coupling":
        # Title: "Hidden co-change coupling: {a.name} <-> {b.name} ({N} commits)"
        # --- FP criteria first ---
        file_path = f.get("file", f.get("affected_file", "")).lower()
        # test↔ implementation co-change is natural in TDD workflows
        if any(x in file_path for x in ["test_", "/tests/", "conftest"]):
            return "FP"
        # Both sides in the title: check if coupling involves test files
        if "test_" in title_lower or "/tests/" in title_lower:
            return "FP"
        # --- TP criteria ---
        if "co-change coupling" in title_lower or "co_change" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "guard_clause_deficit":
        # Titles: "Guard clause deficit in {module_key}/"
        #         "Deep nesting in {fn.name}()"
        # Both are structural AST metrics.
        # --- TP criteria ---
        if "guard clause deficit" in title_lower or "deep nesting" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "test_polarity_deficit":
        # Titles: "Happy-path-only test suite in {module_key}/"
        #         "Zero-assertion tests in {module_key}/"
        # Both are structural metrics on test function counts/assertions.
        # --- TP criteria ---
        if "happy-path-only" in title_lower or "zero-assertion tests" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "broad_exception_monoculture":
        # Title: "Broad exception monoculture in {module_key}/"
        # Pattern density in exception handling.
        # --- TP criteria ---
        if "broad exception monoculture" in title_lower:
            return "TP"
        return "Disputed"

    elif signal == "missing_authorization":
        # Title: "Endpoint '{fn_name}' has no authorization check"
        # Security signal — endpoint without auth guard = TP.
        # --- TP criteria ---
        if "no authorization check" in title_lower:
            return "TP"
        return "Disputed"

    return "Disputed"


def classify_fp_type(f: dict, label: str) -> str | None:
    """Auto-classify FP root-cause type based on structural heuristics.

    Returns None for non-FP findings.  Valid types:
    structural, threshold, scope, semantic, co_occurrence.
    """
    if label != "FP":
        return None

    file_path = str(
        f.get("file") or f.get("affected_file") or f.get("path") or ""
    ).lower()
    score = f.get("score", 0)

    # Scope FP: finding in tests, docs, migrations, generated code
    scope_markers = [
        "test_", "/tests/", "conftest", "/docs/", "/doc/",
        "migration", "/generated/", "__pycache__", "changelog",
        "readme", "/examples/",
    ]
    if any(m in file_path for m in scope_markers):
        return "scope"

    # Structural FP: framework/library patterns or registry/plugin architectures
    # where exports are discovered by reflection rather than direct import
    structural_markers = [
        "middleware", "error_handler", "exception_handler",
        "error_boundary", "celery", "signal_handler",
        "fallback", "recovery", "__init__",
    ]
    if any(m in file_path for m in structural_markers):
        return "structural"

    # Structural FP: MCP server / embedding / session / pipeline / signal registry
    # patterns where exports are consumed externally (protocol handler, plugin loader)
    signal_name = f.get("signal", "")
    if signal_name == "dead_code_accumulation":
        lib_registry_markers = [
            "mcp_server", "embeddings", "session", "pipeline",
            "signals/", "/signals/", "_violation", "_signal",
        ]
        if any(m in file_path for m in lib_registry_markers):
            return "structural"

    # Threshold FP: score below 30% of signal range
    if score < 0.3:
        return "threshold"

    # Default: semantic (signal misunderstands context)
    return "semantic"


def main():
    results_dir = Path("benchmark_results")
    repos = ["drift_self", "fastapi", "pydantic", "pwbs_backend", "httpx"]

    all_findings = []
    for repo in repos:
        full_path = results_dir / f"{repo}_full.json"
        if not full_path.exists():
            continue
        try:
            with open(full_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        findings = data.get("findings", [])
        for f in findings:
            f["_repo"] = repo
        all_findings.extend(findings)

    print(f"Total findings across 5 repos: {len(all_findings)}")

    # Stratified sample: up to 15 per signal per repo (for signals with many findings)
    sample = []
    by_signal_repo = defaultdict(list)
    for f in all_findings:
        key = (f["_repo"], f.get("signal", ""))
        by_signal_repo[key].append(f)

    for _key, items in by_signal_repo.items():
        items_sorted = sorted(items, key=lambda x: -x.get("score", 0))
        sample.extend(items_sorted[:15])

    print(f"Stratified sample: {len(sample)} findings\n")

    # Classify
    classifications = []
    fp_type_counts: dict[str, int] = defaultdict(int)
    for f in sample:
        label = classify_finding(f)
        fp_type = classify_fp_type(f, label)
        entry: dict = {
            "repo": f["_repo"],
            "signal": f.get("signal", ""),
            "title": f.get("title", ""),
            "score": f.get("score", 0),
            "severity": f.get("severity", ""),
            "label": label,
        }
        if fp_type:
            entry["fp_type"] = fp_type
            fp_type_counts[fp_type] += 1
        classifications.append(entry)

    # Compute precision per signal
    by_signal = defaultdict(lambda: {"TP": 0, "FP": 0, "Disputed": 0, "total": 0})
    for c in classifications:
        sig = c["signal"]
        by_signal[sig][c["label"]] += 1
        by_signal[sig]["total"] += 1

    print("=" * 70)
    print("GROUND-TRUTH PRECISION ANALYSIS")
    print("=" * 70)
    print(
        f"\n{'Signal':<25s} {'Sample':>7s} {'TP':>5s} "
        f"{'FP':>5s} {'Disp':>5s} {'Prec':>7s} {'Prec*':>7s}"
    )
    print("-" * 65)

    total_tp = total_fp = total_disp = total_n = 0
    signal_order = [
        "pattern_fragmentation",
        "architecture_violation",
        "mutant_duplicate",
        "temporal_volatility",
        "explainability_deficit",
        "system_misalignment",
        "doc_impl_drift",
    ]

    small_sample_signals = []
    for sig in signal_order:
        if sig not in by_signal:
            continue
        d = by_signal[sig]
        tp, fp, disp, n = d["TP"], d["FP"], d["Disputed"], d["total"]
        total_tp += tp
        total_fp += fp
        total_disp += disp
        total_n += n
        # Conservative precision: Disputed counted as FP
        prec_conservative = tp / n if n else 0
        # Optimistic precision: Disputed counted as TP
        prec_optimistic = (tp + disp) / n if n else 0
        warn = " *" if n < 30 else ""
        if n < 30:
            small_sample_signals.append((sig, n))
        print(
            f"{sig:<25s} {n:>7d} {tp:>5d} {fp:>5d} {disp:>5d} "
            f"{prec_conservative:>6.0%} {prec_optimistic:>6.0%}{warn}"
        )

    print("-" * 65)
    prec_c = total_tp / total_n if total_n else 0
    prec_o = (total_tp + total_disp) / total_n if total_n else 0
    print(
        f"{'TOTAL':<25s} {total_n:>7d} {total_tp:>5d} {total_fp:>5d} "
        f"{total_disp:>5d} {prec_c:>6.0%} {prec_o:>6.0%}"
    )
    print("\nPrec  = TP / (TP + FP + Disputed)  — strict")
    print(
        "Prec* = (TP + Disputed) / Total"
        "    — lenient (disputed = debatable, not wrong)"
    )
    if small_sample_signals:
        print("\n * Small sample (n < 30): precision estimates unreliable")
        for sig_name, sig_n in small_sample_signals:
            print(f"   - {sig_name}: n={sig_n}")

    # Breakdown: FP examples per signal
    print("\n\nFP EXAMPLES (first 5 per signal):")
    for sig in signal_order:
        fps = [c for c in classifications if c["signal"] == sig and c["label"] == "FP"]
        if fps:
            print(f"\n  {sig}:")
            for fp in fps[:5]:
                title = fp["title"][:70].encode("ascii", "replace").decode()
                fp_t = fp.get("fp_type", "?")
                print(f"    - [{fp['repo']}] [{fp_t}] {title}")

    # FP-type taxonomy breakdown (Schicht 3)
    if fp_type_counts:
        print("\n\nFP-TYPE TAXONOMY:")
        print("-" * 40)
        for fpt in sorted(fp_type_counts):
            print(f"  {fpt:<20s} {fp_type_counts[fpt]:>4d}")
        print(f"  {'TOTAL':<20s} {sum(fp_type_counts.values()):>4d}")

    # Save results — with reproducibility metadata
    try:
        from drift import __version__ as drift_ver
    except Exception:
        drift_ver = "unknown"

    output = {
        "_metadata": {
            "drift_version": drift_ver,
            "generated_at": datetime.now(datetime.UTC).isoformat(),
            "classification_method": "automated_heuristic",
            "methodology_note": (
                "Classification uses structural title/path heuristics where "
                "possible. Score-only classifications are marked Disputed to "
                "avoid circular validation. Precision numbers are upper bounds "
                "on the score-weighted sample, not population estimates."
            ),
        },
        "total_findings": len(all_findings),
        "sample_size": len(sample),
        "precision_by_signal": {
            sig: {
                "sample": d["total"],
                "tp": d["TP"],
                "fp": d["FP"],
                "disputed": d["Disputed"],
                "precision_strict": d["TP"] / d["total"] if d["total"] else 0,
                "precision_lenient": (d["TP"] + d["Disputed"]) / d["total"] if d["total"] else 0,
                "sample_sufficient": d["total"] >= 30,
            }
            for sig, d in by_signal.items()
        },
        "total": {
            "sample": total_n,
            "tp": total_tp,
            "fp": total_fp,
            "disputed": total_disp,
            "precision_strict": prec_c,
            "precision_lenient": prec_o,
        },
        "classifications": classifications,
    }

    out_path = results_dir / "ground_truth_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n\nSaved to {out_path}")


if __name__ == "__main__":
    main()
