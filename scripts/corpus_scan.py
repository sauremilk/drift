#!/usr/bin/env python3
"""H2 instrument: Corpus-Scan — batch-scan oracle repos and compute signal correlation matrix.

Clones all repos from oracle_repos.json (shallow), runs drift analyze on each,
collects per-repo per-signal scores, and computes a Pearson correlation matrix
plus PCA variance-explained to assess construct validity.

Usage:
    python scripts/corpus_scan.py
    python scripts/corpus_scan.py --repos benchmarks/oracle_repos.json
    python scripts/corpus_scan.py --skip-clone   # re-use cached clones in work_artifacts/

Outputs:
    benchmark_results/corpus_signal_matrix.json
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPOS = REPO_ROOT / "benchmarks" / "oracle_repos.json"
RESULTS_DIR = REPO_ROOT / "benchmark_results"
CLONE_CACHE = REPO_ROOT / "work_artifacts" / "corpus_clones"


def _load_repos(repos_file: Path) -> list[dict[str, str]]:
    if not repos_file.exists():
        sys.exit(f"Repos file not found: {repos_file}")
    data = json.loads(repos_file.read_text(encoding="utf-8"))
    return data["repos"]


def _shallow_clone(url: str, ref: str, dest: Path) -> bool:
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", ref,
             "--single-branch", url, str(dest)],
            check=True, capture_output=True, timeout=300,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"  clone failed: {exc}", file=sys.stderr)
        return False


def _run_drift(repo_path: Path) -> dict[str, Any] | None:
    """Run drift analyze on a repo and return parsed JSON result."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "drift", "analyze",
             "--repo", str(repo_path), "--format", "json", "--exit-zero"],
            capture_output=True, text=True, timeout=600,
        )
        text = result.stdout
        # Extract JSON from potential trailing Rich output
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        print(f"  drift failed: {exc}", file=sys.stderr)
    return None


def _extract_signal_scores(drift_result: dict[str, Any]) -> dict[str, float]:
    """Extract per-signal aggregate scores from drift output."""
    scores: dict[str, float] = {}
    findings = drift_result.get("findings", [])
    # Aggregate: mean score per signal
    by_signal: dict[str, list[float]] = {}
    for f in findings:
        sig = f.get("signal", "")
        score = f.get("score", 0.0)
        if sig:
            by_signal.setdefault(sig, []).append(score)
    for sig, vals in by_signal.items():
        scores[sig] = sum(vals) / len(vals) if vals else 0.0
    return scores


def _pearson_r(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(xs)
    if n < 3:
        return float("nan")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0
    return cov / denom


def _simple_pca_variance(matrix: list[list[float]]) -> list[float]:
    """Approximate PCA via eigenvalue decomposition of correlation matrix.

    Uses a power-iteration approach for the dominant eigenvalues.
    Returns variance-explained ratios for the first min(6, n_signals) components.
    """
    n = len(matrix)
    if n == 0:
        return []

    # Correlation matrix is already provided; compute eigenvalues via
    # numpy-free approach: iterative deflation + power iteration.
    import copy
    mat = copy.deepcopy(matrix)

    eigenvalues: list[float] = []
    max_components = min(6, n)

    for _ in range(max_components):
        # Power iteration
        vec = [1.0 / math.sqrt(n)] * n
        for _iter in range(200):
            new_vec = [sum(mat[i][j] * vec[j] for j in range(n)) for i in range(n)]
            norm = math.sqrt(sum(v * v for v in new_vec))
            if norm < 1e-12:
                break
            new_vec = [v / norm for v in new_vec]
            # Check convergence
            diff = sum((a - b) ** 2 for a, b in zip(new_vec, vec, strict=False))
            vec = new_vec
            if diff < 1e-10:
                break

        eigenvalue = sum(vec[i] * sum(mat[i][j] * vec[j] for j in range(n)) for i in range(n))
        eigenvalues.append(max(eigenvalue, 0.0))

        # Deflate
        for i in range(n):
            for j in range(n):
                mat[i][j] -= eigenvalue * vec[i] * vec[j]

    total = sum(eigenvalues)
    if total <= 0:
        return [0.0] * len(eigenvalues)
    return [ev / total for ev in eigenvalues]


def corpus_scan(repos_file: Path, skip_clone: bool = False) -> None:
    """Run corpus scan and produce signal matrix artifact."""
    repos = _load_repos(repos_file)
    print(f"Corpus: {len(repos)} repos from {repos_file.name}")

    all_scores: dict[str, dict[str, float]] = {}  # repo_name -> {signal: score}

    for repo_info in repos:
        name = repo_info["name"]
        url = repo_info["url"]
        ref = repo_info.get("ref", "main")
        print(f"\n[{name}] {url} @ {ref}")

        if skip_clone:
            repo_path = CLONE_CACHE / name
            if not repo_path.exists():
                print("  cache miss, skipping (use without --skip-clone)")
                continue
        else:
            CLONE_CACHE.mkdir(parents=True, exist_ok=True)
            repo_path = CLONE_CACHE / name
            if repo_path.exists():
                print("  using cached clone")
            else:
                if not _shallow_clone(url, ref, repo_path):
                    continue

        print("  running drift analyze ...")
        result = _run_drift(repo_path)
        if result is None:
            print("  no result, skipping")
            continue

        scores = _extract_signal_scores(result)
        all_scores[name] = scores
        n_findings = len(result.get("findings", []))
        print(f"  {n_findings} findings, {len(scores)} signals active")

    if len(all_scores) < 3:
        print(f"\nInsufficient repos with results ({len(all_scores)}). Need ≥ 3.", file=sys.stderr)
        sys.exit(1)

    # Build signal list (union of all observed signals)
    all_signals = sorted(set(s for scores in all_scores.values() for s in scores))
    repo_names = sorted(all_scores)

    # Build matrix: repos x signals
    score_matrix: list[list[float]] = []
    for repo in repo_names:
        row = [all_scores[repo].get(sig, 0.0) for sig in all_signals]
        score_matrix.append(row)

    # Correlation matrix (signal x signal)
    n_signals = len(all_signals)
    corr_matrix: list[list[float]] = [[0.0] * n_signals for _ in range(n_signals)]
    for i in range(n_signals):
        for j in range(n_signals):
            col_i = [score_matrix[r][i] for r in range(len(repo_names))]
            col_j = [score_matrix[r][j] for r in range(len(repo_names))]
            corr_matrix[i][j] = round(_pearson_r(col_i, col_j), 4)

    # PCA
    variance_explained = _simple_pca_variance(corr_matrix)
    cumulative = []
    running = 0.0
    for v in variance_explained:
        running += v
        cumulative.append(round(running, 4))

    # Find n_components for 70% threshold
    n_components_70 = next(
        (i + 1 for i, c in enumerate(cumulative) if c >= 0.70),
        len(variance_explained),
    )

    # Print
    print("\n" + "=" * 72)
    print("CORPUS SIGNAL MATRIX (H2)")
    print("=" * 72)
    print(f"  Repos analyzed:            {len(repo_names)}")
    print(f"  Signals observed:          {n_signals}")
    print(f"  PCA components for ≥70%:   {n_components_70}")
    print("  Variance explained (top 6):")
    for i, (ve, cum) in enumerate(zip(variance_explained, cumulative, strict=False)):
        print(f"    PC{i+1}: {ve:.1%}  (cumulative: {cum:.1%})")

    gate = n_components_70 <= 3
    print(f"\n  H2 Gate (≤3 components for 70%): {'PASS' if gate else 'FAIL'}")
    if not gate:
        print(f"  → {n_components_70} components needed — signals may measure "
              f"heterogeneous constructs")

    # Artifact
    artifact = {
        "n_repos": len(repo_names),
        "repos": repo_names,
        "signals": all_signals,
        "score_matrix": {
            repo: {sig: all_scores[repo].get(sig, 0.0) for sig in all_signals}
            for repo in repo_names
        },
        "correlation_matrix": {
            all_signals[i]: {
                all_signals[j]: corr_matrix[i][j]
                for j in range(n_signals)
            }
            for i in range(n_signals)
        },
        "pca_variance_explained": [round(v, 4) for v in variance_explained],
        "pca_cumulative": cumulative,
        "pca_n_components_70pct_threshold": n_components_70,
        "h2_gate_pass": gate,
    }
    out_path = RESULTS_DIR / "corpus_signal_matrix.json"
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Artifact written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="H2: Corpus scan and signal correlation")
    parser.add_argument(
        "--repos", type=Path, default=DEFAULT_REPOS,
        help=f"Path to repos JSON file (default: {DEFAULT_REPOS.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--skip-clone", action="store_true",
        help="Re-use cached clones in work_artifacts/corpus_clones/",
    )
    args = parser.parse_args()
    corpus_scan(repos_file=args.repos, skip_clone=args.skip_clone)


if __name__ == "__main__":
    main()
