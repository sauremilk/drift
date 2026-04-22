#!/usr/bin/env python3
"""Enforce consistency between drift's signal model in code and public documentation.

Checks that public-facing documentation agrees with the authoritative signal
model defined in src/drift/config.py.  Designed to run alongside
check_release_discipline.py in pre-push hooks and CI.

Exit 0 = all checks pass.
Exit 1 = critical inconsistency (blocks push/merge).

Use ``--json`` to emit machine-readable output (one JSON array of
discrepancy objects) for downstream automation (doc-consistency workflow).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Structured discrepancy record
# ---------------------------------------------------------------------------

_JSON_MODE = "--json" in sys.argv


def _discrepancy(
    *,
    check_id: str,
    category: str,
    severity: str,
    source_file: str,
    description: str,
    expected: str = "",
    actual: str = "",
    fix_suggestion: str = "",
    source_line: int | None = None,
) -> dict[str, Any]:
    """Build a machine-readable discrepancy dict."""
    rec: dict[str, Any] = {
        "check_id": check_id,
        "category": category,
        "severity": severity,
        "source_file": source_file,
        "description": description,
        "expected": expected,
        "actual": actual,
        "fix_suggestion": fix_suggestion,
    }
    if source_line is not None:
        rec["source_line"] = source_line
    return rec


def _fail(message: str) -> None:
    if not _JSON_MODE:
        print(f"FAIL: {message}", flush=True)


def _ok(message: str) -> None:
    if not _JSON_MODE:
        print(f"OK: {message}", flush=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Source-of-truth: extract signal weights from config.py
# ---------------------------------------------------------------------------


def _extract_config_weights() -> dict[str, float]:
    """Parse SignalWeights defaults from src/drift/config/_schema.py using AST."""
    config_path = _repo_root() / "src" / "drift" / "config" / "_schema.py"
    tree = ast.parse(config_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SignalWeights":
            weights: dict[str, float] = {}
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.value is not None
                    and isinstance(stmt.value, ast.Constant)
                ):
                    val = stmt.value.value
                    if isinstance(val, (int, float)):
                        weights[stmt.target.id] = float(val)
            return weights

    _fail("Could not find SignalWeights class in config.py")
    sys.exit(1)


def _extract_pyproject_version() -> str:
    pyproject = _repo_root() / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


# ---------------------------------------------------------------------------
# Check 1: Signal count in public docs
# ---------------------------------------------------------------------------

_SIGNAL_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s+scoring\s+signal", re.IGNORECASE),
    re.compile(r"(\d+)\s+signal\s+families", re.IGNORECASE),
]


def _check_signal_count(expected: int) -> tuple[list[str], list[dict[str, Any]]]:
    """Verify docs claim the correct number of scoring signals."""
    errors: list[str] = []
    discs: list[dict[str, Any]] = []
    root = _repo_root()
    doc_files = [
        root / "docs-site" / "index.md",
        root / "docs-site" / "trust-evidence.md",
        root / "docs-site" / "algorithms" / "signals.md",
        root / "docs-site" / "benchmarking.md",
        root / "docs" / "OUTREACH.md",
    ]
    for path in doc_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _SIGNAL_COUNT_PATTERNS:
            for m in pattern.finditer(text):
                claimed = int(m.group(1))
                if claimed != expected:
                    rel = str(path.relative_to(root))
                    msg = (
                        f"{rel}: claims {claimed} signals, expected {expected} "
                        f"(match: '{m.group(0)}')"
                    )
                    errors.append(msg)
                    discs.append(
                        _discrepancy(
                            check_id="signal_count_mismatch",
                            category="signal_count",
                            severity="high",
                            source_file=rel,
                            expected=str(expected),
                            actual=str(claimed),
                            description=msg,
                            fix_suggestion=(
                                f"Update signal count in {rel}"
                                f" from {claimed} to {expected}"
                            ),
                        )
                    )
    return errors, discs


# ---------------------------------------------------------------------------
# Check 2: Weight table in scoring.md matches config.py
# ---------------------------------------------------------------------------

_WEIGHT_ROW_RE = re.compile(
    r"\|\s*[^|]+\((\w+)\)\s*\|\s*([\d.]+)\s*\|",
)


def _check_scoring_weights(
    config_weights: dict[str, float],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Verify the weight table in scoring.md matches config.py."""
    errors: list[str] = []
    discs: list[dict[str, Any]] = []
    scoring_md = _repo_root() / "docs-site" / "algorithms" / "scoring.md"
    if not scoring_md.exists():
        return errors, discs

    text = scoring_md.read_text(encoding="utf-8")

    # Map short codes to config keys
    code_to_key = {
        "PFS": "pattern_fragmentation",
        "AVS": "architecture_violation",
        "MDS": "mutant_duplicate",
        "TVS": "temporal_volatility",
        "EDS": "explainability_deficit",
        "SMS": "system_misalignment",
        "DIA": "doc_impl_drift",
        "BEM": "broad_exception_monoculture",
        "TPD": "test_polarity_deficit",
        "GCD": "guard_clause_deficit",
        "NBV": "naming_contract_violation",
        "BAT": "bypass_accumulation",
        "ECM": "exception_contract_drift",
    }

    for m in _WEIGHT_ROW_RE.finditer(text):
        code = m.group(1)
        doc_weight = float(m.group(2))
        config_key = code_to_key.get(code)
        if config_key is None:
            continue
        expected = config_weights.get(config_key)
        if expected is not None and abs(doc_weight - expected) > 0.01:
            msg = f"scoring.md: {code} weight={doc_weight}, config.py={expected}"
            errors.append(msg)
            discs.append(
                _discrepancy(
                    check_id=f"weight_mismatch_{code.lower()}",
                    category="weight_table",
                    severity="high",
                    source_file="docs-site/algorithms/scoring.md",
                    expected=str(expected),
                    actual=str(doc_weight),
                    description=msg,
                    fix_suggestion=(
                        f"Update {code} weight in scoring.md"
                        f" from {doc_weight} to {expected}"
                    ),
                )
            )

    return errors, discs


# ---------------------------------------------------------------------------
# Check 3: drift.example.yaml weights match config.py
# ---------------------------------------------------------------------------

_YAML_WEIGHT_RE = re.compile(r"^\s+([\w_]+):\s+([\d.]+)", re.MULTILINE)


def _check_example_yaml(config_weights: dict[str, float]) -> tuple[list[str], list[dict[str, Any]]]:
    """Verify drift.example.yaml weight values match config.py defaults."""
    errors: list[str] = []
    discs: list[dict[str, Any]] = []
    yaml_path = _repo_root() / "drift.example.yaml"
    if not yaml_path.exists():
        return errors, discs

    text = yaml_path.read_text(encoding="utf-8")
    in_weights = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "weights:":
            in_weights = True
            continue
        if in_weights and stripped and not stripped.startswith("#"):
            m = _YAML_WEIGHT_RE.match(line)
            if m:
                key = m.group(1)
                yaml_val = float(m.group(2))
                expected = config_weights.get(key)
                if expected is not None and abs(yaml_val - expected) > 0.01:
                    msg = f"drift.example.yaml: {key}={yaml_val}, config.py={expected}"
                    errors.append(msg)
                    discs.append(
                        _discrepancy(
                            check_id=f"yaml_weight_mismatch_{key}",
                            category="yaml_weights",
                            severity="medium",
                            source_file="drift.example.yaml",
                            expected=str(expected),
                            actual=str(yaml_val),
                            description=msg,
                            fix_suggestion=(
                                f"Update {key} in drift.example.yaml"
                                f" from {yaml_val} to {expected}"
                            ),
                        )
                    )
            elif not stripped.startswith("#"):
                in_weights = False

    return errors, discs


# ---------------------------------------------------------------------------
# Check 4: SECURITY.md supported version includes current major.minor
# ---------------------------------------------------------------------------


def _check_security_version(version: str) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    discs: list[dict[str, Any]] = []
    security_md = _repo_root() / "SECURITY.md"
    if not security_md.exists():
        return errors, discs

    text = security_md.read_text(encoding="utf-8")
    major_minor = ".".join(version.split(".")[:2])
    pattern = f"{major_minor}.x"
    if pattern not in text:
        msg = f"SECURITY.md does not list {pattern} as supported (current version: {version})"
        errors.append(msg)
        discs.append(
            _discrepancy(
                check_id="security_version_missing",
                category="version_ref",
                severity="medium",
                source_file="SECURITY.md",
                expected=pattern,
                actual="(not listed)",
                description=msg,
                fix_suggestion=f"Add '{pattern}' to the supported versions table in SECURITY.md",
            )
        )
    return errors, discs


# ---------------------------------------------------------------------------
# Check 5: llms.txt is regenerable from authoritative sources (ADR-092)
# ---------------------------------------------------------------------------
#
# ``llms.txt`` is fully autogenerated from ``pyproject.toml`` (version) and
# ``src/drift/signal_registry.py`` (signal table). Rather than re-parsing the
# file here, we delegate to the generator's own ``--check`` mode. That keeps
# a single source of truth for the layout (``scripts/generate_llms_txt.py``)
# and eliminates the risk of partial signal coverage in a handmaintained
# ``code_to_key`` mapping.


def _check_llms_txt(_config_weights: dict[str, float]) -> tuple[list[str], list[dict[str, Any]]]:
    """Delegate llms.txt validation to scripts/generate_llms_txt.py --check."""
    errors: list[str] = []
    discs: list[dict[str, Any]] = []

    generator = _repo_root() / "scripts" / "generate_llms_txt.py"
    if not generator.exists():
        # Dev-clone without the generator should not hard-fail the gate.
        return errors, discs

    result = subprocess.run(  # noqa: S603 -- fixed trusted script path
        [sys.executable, str(generator), "--check"],
        capture_output=True,
        text=True,
        cwd=str(_repo_root()),
    )
    if result.returncode != 0:
        msg = "llms.txt drifted from signal_registry / pyproject.toml"
        errors.append(msg)
        discs.append(
            _discrepancy(
                check_id="llms_txt_regenerable",
                category="weight_table",
                severity="medium",
                source_file="llms.txt",
                expected="generate_llms_txt.py --check passes",
                actual="diff detected",
                description=(result.stderr or result.stdout or msg).strip(),
                fix_suggestion="Run: python scripts/generate_llms_txt.py --write",
            )
        )

    return errors, discs


# ---------------------------------------------------------------------------
# Check 6: version references in llms.txt (delegated to Check 5)
# ---------------------------------------------------------------------------
#
# The version check is implicitly covered by Check 5 (the generator renders
# ``Release status: v{pyproject version}`` and ``--check`` fails on any
# mismatch). ``_check_version_refs`` is kept as a no-op shim so the public
# entry point in this script stays stable for downstream callers.


def _check_version_refs(_version: str) -> tuple[list[str], list[dict[str, Any]]]:
    """No-op: llms.txt version drift is caught by Check 5 (generator --check)."""
    return [], []


# ---------------------------------------------------------------------------
# Check 7: Python version requirement in installation docs
# ---------------------------------------------------------------------------


def _check_python_version_docs() -> tuple[list[str], list[dict[str, Any]]]:
    """Verify installation docs match pyproject.toml requires-python."""
    errors: list[str] = []
    discs: list[dict[str, Any]] = []
    root = _repo_root()

    pyproject = root / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    requires_python = data.get("project", {}).get("requires-python", "")
    if not requires_python:
        return errors, discs

    install_md = root / "docs-site" / "getting-started" / "installation.md"
    if not install_md.exists():
        return errors, discs

    text = install_md.read_text(encoding="utf-8")
    # Match patterns like "Python 3.11+" or "Python >=3.11"
    py_ver_re = re.compile(r"Python\s+([\d.]+)\+|Python\s*>=\s*([\d.]+)")
    for m in py_ver_re.finditer(text):
        claimed = m.group(1) or m.group(2)
        # Extract version from requires-python like ">=3.11"
        req_match = re.search(r"([\d.]+)", requires_python)
        if req_match:
            expected = req_match.group(1)
            if claimed != expected:
                msg = (
                    f"installation.md: claims Python {claimed}+,"
                    f" pyproject.toml requires >={expected}"
                )
                errors.append(msg)
                discs.append(
                    _discrepancy(
                        check_id="python_version_mismatch",
                        category="version_ref",
                        severity="medium",
                        source_file="docs-site/getting-started/installation.md",
                        expected=f">={expected}",
                        actual=f"{claimed}+",
                        description=msg,
                        fix_suggestion=(
                            f"Update Python version in"
                            f" installation.md from {claimed}"
                            f" to {expected}"
                        ),
                    )
                )

    return errors, discs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    config_weights = _extract_config_weights()
    # Count only signals with weight > 0 as scoring-active.
    # Signals at weight 0 (incl. TVS) are report-only.
    scoring_count = sum(1 for weight in config_weights.values() if weight > 0)
    version = _extract_pyproject_version()

    all_errors: list[str] = []
    all_discs: list[dict[str, Any]] = []

    def _collect(result: tuple[list[str], list[dict[str, Any]]]) -> None:
        errs, discs = result
        all_errors.extend(errs)
        all_discs.extend(discs)

    # Check 1: signal count
    _collect(_check_signal_count(scoring_count))

    # Check 2: scoring.md weights
    _collect(_check_scoring_weights(config_weights))

    # Check 3: example yaml
    _collect(_check_example_yaml(config_weights))

    # Check 4: security version
    _collect(_check_security_version(version))

    # Check 5: llms.txt weights
    _collect(_check_llms_txt(config_weights))

    # Check 6: version references
    _collect(_check_version_refs(version))

    # Check 7: Python version in docs
    _collect(_check_python_version_docs())

    if _JSON_MODE:
        print(json.dumps(all_discs, indent=2))
        return 1 if all_discs else 0

    if all_errors:
        print(f"\n{'='*60}", flush=True)
        print("Model consistency check FAILED", flush=True)
        print(f"{'='*60}", flush=True)
        for err in all_errors:
            _fail(err)
        print(f"\n{len(all_errors)} inconsistency(ies) found.", flush=True)
        return 1

    _ok(f"Signal model consistent: {scoring_count} scoring signals, version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
