#!/usr/bin/env python3
"""Build an ISO/IEC 25010 quality scorecard from existing drift artifacts.

Usage:
    python scripts/quality_scorecard.py          # Dry-run: print summary
    python scripts/quality_scorecard.py --apply  # Write benchmark_results/quality_scorecard.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "benchmark_results" / "quality_scorecard.json"

KPI_SNAPSHOT = REPO_ROOT / "benchmark_results" / "kpi_snapshot.json"
MUTATION = REPO_ROOT / "benchmark_results" / "mutation_benchmark.json"
COVERAGE_XML = REPO_ROOT / "coverage.xml"
PERF_BUDGET = REPO_ROOT / "benchmarks" / "perf_budget.json"

AUDIT_FILES = [
    REPO_ROOT / "audit_results" / "fmea_matrix.md",
    REPO_ROOT / "audit_results" / "stride_threat_model.md",
    REPO_ROOT / "audit_results" / "fault_trees.md",
    REPO_ROOT / "audit_results" / "risk_register.md",
]

PORTABILITY_MARKERS = [
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "conda.recipe" / "meta.yaml",
    REPO_ROOT / "pyproject.toml",
]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_coverage_ratio(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
        line_rate = root.attrib.get("line-rate")
        if line_rate is None:
            return None
        return _clamp(float(line_rate))
    except (ElementTree.ParseError, OSError, ValueError):
        return None


def _confidence(*, present: int, total: int) -> str:
    ratio = present / total if total else 0.0
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"


def _dimension(
    score: float,
    confidence: str,
    sources: list[str],
    gaps: list[str],
) -> dict[str, Any]:
    return {
        "score": round(_clamp(score), 4),
        "confidence": confidence,
        "sources": sources,
        "gaps": gaps,
    }


def build_scorecard(repo_root: Path) -> dict[str, Any]:
    """Build scorecard from repository-local quality artifacts."""
    kpi_data = _read_json(repo_root / "benchmark_results" / "kpi_snapshot.json")
    mutation_data = _read_json(repo_root / "benchmark_results" / "mutation_benchmark.json")
    perf_budget = _read_json(repo_root / "benchmarks" / "perf_budget.json")
    coverage_ratio = _read_coverage_ratio(repo_root / "coverage.xml")

    dimensions: dict[str, dict[str, Any]] = {}

    # Functional suitability: precision/recall + mutation recall.
    aggregate_f1 = (
        kpi_data.get("precision_recall", {}).get("aggregate_f1")
        if isinstance(kpi_data, dict)
        else None
    )
    mutation_recall = (
        mutation_data.get("overall_recall")
        if isinstance(mutation_data, dict)
        else None
    )

    functional_sources: list[str] = []
    functional_gaps: list[str] = []
    functional_parts: list[float] = []

    if isinstance(aggregate_f1, (int, float)):
        functional_parts.append(_clamp(float(aggregate_f1)))
        functional_sources.append("benchmark_results/kpi_snapshot.json:precision_recall.aggregate_f1")
    else:
        functional_gaps.append("aggregate_f1 missing in kpi_snapshot")

    if isinstance(mutation_recall, (int, float)):
        functional_parts.append(_clamp(float(mutation_recall)))
        functional_sources.append("benchmark_results/mutation_benchmark.json:overall_recall")
    else:
        functional_gaps.append("mutation overall_recall missing")

    functional_score = sum(functional_parts) / len(functional_parts) if functional_parts else 0.25
    dimensions["functional_suitability"] = _dimension(
        functional_score,
        _confidence(present=len(functional_parts), total=2),
        functional_sources,
        functional_gaps,
    )

    # Performance efficiency: currently budget coverage only (measurement follows).
    perf_keys = {
        "wall_clock_budget_seconds",
        "max_iterations",
        "benchmark_runs",
    }
    present_perf = sum(1 for key in perf_keys if key in perf_budget)
    perf_score = present_perf / len(perf_keys)
    perf_gaps = [] if present_perf == len(perf_keys) else ["missing entries in perf_budget.json"]
    perf_sources = ["benchmarks/perf_budget.json"] if perf_budget else []
    if not perf_sources:
        perf_gaps.append("perf budget missing")
    dimensions["performance_efficiency"] = _dimension(
        perf_score if perf_sources else 0.2,
        _confidence(present=present_perf, total=len(perf_keys)),
        perf_sources,
        perf_gaps,
    )

    # Usability: docs/help proxies for now (explicitly low confidence).
    usability_paths = [
        repo_root / "README.md",
        repo_root / "docs",
        repo_root / "mkdocs.yml",
    ]
    usability_present = sum(1 for path in usability_paths if path.exists())
    dimensions["usability"] = _dimension(
        usability_present / len(usability_paths),
        "low",
        ["README.md", "docs/", "mkdocs.yml"] if usability_present else [],
        ["no direct UX metrics yet (TTFR/help coverage pending)"],
    )

    # Reliability: coverage + smoke test presence.
    smoke_test_path = repo_root / "tests" / "test_smoke_real_repos.py"
    reliability_parts: list[float] = []
    reliability_sources: list[str] = []
    reliability_gaps: list[str] = []
    if coverage_ratio is not None:
        reliability_parts.append(coverage_ratio)
        reliability_sources.append("coverage.xml:line-rate")
    else:
        reliability_gaps.append("coverage.xml line-rate missing")

    if smoke_test_path.exists():
        reliability_parts.append(1.0)
        reliability_sources.append("tests/test_smoke_real_repos.py")
    else:
        reliability_gaps.append("smoke test file missing")

    reliability_score = (
        sum(reliability_parts) / len(reliability_parts)
        if reliability_parts
        else 0.2
    )
    dimensions["reliability"] = _dimension(
        reliability_score,
        _confidence(present=len(reliability_parts), total=2),
        reliability_sources,
        reliability_gaps,
    )

    # Security: required audit/security files.
    security_required = AUDIT_FILES + [
        repo_root / "SECURITY.md",
        repo_root / "pip-audit-requirements.txt",
    ]
    security_present = [path for path in security_required if path.exists()]
    security_score = len(security_present) / len(security_required)
    dimensions["security"] = _dimension(
        security_score,
        _confidence(present=len(security_present), total=len(security_required)),
        [str(path.relative_to(repo_root)).replace("\\", "/") for path in security_present],
        (
            []
            if len(security_present) == len(security_required)
            else ["one or more security artifacts missing"]
        ),
    )

    # Compatibility: contracts and CI workflows as integration proxies.
    compatibility_paths = [
        repo_root / "tests" / "test_sarif_contract.py",
        repo_root / "drift.output.schema.json",
        repo_root / ".github" / "workflows" / "ci.yml",
    ]
    compatibility_present = [path for path in compatibility_paths if path.exists()]
    dimensions["compatibility"] = _dimension(
        len(compatibility_present) / len(compatibility_paths),
        _confidence(present=len(compatibility_present), total=len(compatibility_paths)),
        [str(path.relative_to(repo_root)).replace("\\", "/") for path in compatibility_present],
        (
            []
            if len(compatibility_present) == len(compatibility_paths)
            else ["compatibility contract coverage incomplete"]
        ),
    )

    # Maintainability: inverse self drift score + coverage.
    drift_score = (
        kpi_data.get("self_analysis", {}).get("drift_score")
        if isinstance(kpi_data, dict)
        else None
    )
    maintainability_parts: list[float] = []
    maintainability_sources: list[str] = []
    maintainability_gaps: list[str] = []
    if isinstance(drift_score, (int, float)):
        maintainability_parts.append(_clamp(1.0 - float(drift_score)))
        maintainability_sources.append("benchmark_results/kpi_snapshot.json:self_analysis.drift_score")
    else:
        maintainability_gaps.append("self_analysis drift_score missing")

    if coverage_ratio is not None:
        maintainability_parts.append(coverage_ratio)
        maintainability_sources.append("coverage.xml:line-rate")

    maintainability_score = (
        sum(maintainability_parts) / len(maintainability_parts) if maintainability_parts else 0.25
    )
    dimensions["maintainability"] = _dimension(
        maintainability_score,
        _confidence(present=len(maintainability_parts), total=2),
        maintainability_sources,
        maintainability_gaps,
    )

    # Portability: packaging/runtime markers.
    portability_present = [path for path in PORTABILITY_MARKERS if path.exists()]
    dimensions["portability"] = _dimension(
        len(portability_present) / len(PORTABILITY_MARKERS),
        _confidence(present=len(portability_present), total=len(PORTABILITY_MARKERS)),
        [str(path.relative_to(repo_root)).replace("\\", "/") for path in portability_present],
        (
            []
            if len(portability_present) == len(PORTABILITY_MARKERS)
            else ["portability markers incomplete"]
        ),
    )

    scores = [float(entry["score"]) for entry in dimensions.values()]
    present_sources = sum(1 for entry in dimensions.values() if entry["sources"])

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "standard": "ISO/IEC 25010",
        "version": "v1",
        "overall_score": round(sum(scores) / len(scores), 4),
        "coverage_ratio": round(present_sources / len(dimensions), 4),
        "dimensions": dimensions,
        "notes": [
            "This scorecard is an aggregate proxy model from existing drift artifacts.",
            "Usability metrics currently use documentation/help proxies and should be refined.",
        ],
    }


def _summary(scorecard: dict[str, Any]) -> str:
    lines = [
        "ISO/IEC 25010 Quality Scorecard",
        "=" * 32,
        f"overall_score:  {scorecard['overall_score']:.4f}",
        f"coverage_ratio: {scorecard['coverage_ratio']:.4f}",
        "",
    ]
    for name, entry in scorecard["dimensions"].items():
        lines.append(f"- {name}: {entry['score']:.4f} ({entry['confidence']})")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build ISO/IEC 25010 quality scorecard"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write scorecard JSON to benchmark_results",
    )
    args = parser.parse_args()

    scorecard = build_scorecard(REPO_ROOT)
    print(_summary(scorecard))

    if args.apply:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(scorecard, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()