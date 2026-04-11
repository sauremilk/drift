"""Check that signal/ingestion/output changes have matching audit updates.

Usage: python scripts/check_risk_audit.py [--diff-base <ref>] [--content-check]

Exit 0  = compliant (or no signal changes detected)
Exit 1  = signal changes found without matching audit updates
Exit 2  = audit content validation failed (--content-check mode)

This script is called by:
  - .githooks/pre-push  (local enforcement)
  - .github/workflows/ci.yml  (remote enforcement)
"""

from __future__ import annotations

import re
import subprocess
import sys

SIGNAL_PATHS = ("src/drift/signals/", "src/drift/ingestion/", "src/drift/output/")
AUDIT_ARTIFACTS = (
    "audit_results/fmea_matrix.md",
    "audit_results/stride_threat_model.md",
    "audit_results/fault_trees.md",
    "audit_results/risk_register.md",
)

# Paths that are exempt from the audit gate (non-behavioral changes)
EXEMPT_PATTERNS = ("__pycache__", ".pyc", "__init__.py")


def _get_changed_files(diff_base: str | None) -> list[str]:
    """Return list of changed files vs diff_base or HEAD~1."""
    if diff_base:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", diff_base, "HEAD"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _is_signal_change(filepath: str) -> bool:
    """Check if a file is in a signal-relevant path."""
    if any(exempt in filepath for exempt in EXEMPT_PATTERNS):
        return False
    return any(filepath.startswith(prefix) for prefix in SIGNAL_PATHS)


def _is_audit_change(filepath: str) -> bool:
    """Check if a file is an audit artifact."""
    return filepath in AUDIT_ARTIFACTS


def _check_audit_artifacts_exist() -> list[str]:
    """Verify all four audit artifacts exist on disk."""
    import os

    missing = []
    for artifact in AUDIT_ARTIFACTS:
        if not os.path.isfile(artifact):
            missing.append(artifact)
    return missing


# ---------------------------------------------------------------------------
# Content validation (M4: FTA measure — structural checks beyond existence)
# ---------------------------------------------------------------------------

# FMEA: must have a markdown table with Signal | ... | RPN | Status columns
_FMEA_TABLE_RE = re.compile(
    r"^\|.*Signal.*\|.*Failure Mode.*\|.*RPN.*\|", re.MULTILINE | re.IGNORECASE
)
_FMEA_ROW_RE = re.compile(
    r"^\|\s*[A-Za-z]\w+.*\|.*\|", re.MULTILINE  # Signal ID starting with letter, not separator
)

# Risk Register: must have structured entries with Risk ID and Mitigation
_RISK_ID_RE = re.compile(r"Risk ID:\s*RISK-\w+", re.MULTILINE)
_RISK_MITIGATION_RE = re.compile(r"Mitigation:", re.MULTILINE | re.IGNORECASE)

# Fault Trees: must have Top Event and either MCS table or tree diagram
_FTA_TOP_EVENT_RE = re.compile(r"Top Event|TE-\d+", re.MULTILINE | re.IGNORECASE)
_FTA_STRUCTURE_RE = re.compile(r"MCS|AND-Gate|OR-Gate|Minimal Cut", re.MULTILINE | re.IGNORECASE)

# STRIDE: must have STRIDE review section with S/T/R/I/D/E items
_STRIDE_REVIEW_RE = re.compile(r"STRIDE review:", re.MULTILINE | re.IGNORECASE)
_STRIDE_ITEMS_RE = re.compile(
    r"[STRIDE]\s*\((?:Spoofing|Tampering|Repudiation|Information|Denial|Elevation)",
    re.MULTILINE,
)


def _validate_fmea_content(filepath: str) -> list[str]:
    """Check FMEA matrix has structural integrity."""
    issues: list[str] = []
    try:
        content = open(filepath, encoding="utf-8").read()
    except OSError:
        return [f"Cannot read {filepath}"]

    if not _FMEA_TABLE_RE.search(content):
        issues.append("No FMEA table header found (expected: Signal | Failure Mode | ... | RPN)")
    if not _FMEA_ROW_RE.search(content):
        issues.append("No FMEA data rows found (expected signal ID rows)")
    return issues


def _validate_risk_register_content(filepath: str) -> list[str]:
    """Check risk register has structured entries."""
    issues: list[str] = []
    try:
        content = open(filepath, encoding="utf-8").read()
    except OSError:
        return [f"Cannot read {filepath}"]

    if not _RISK_ID_RE.search(content):
        issues.append("No Risk ID entries found (expected: Risk ID: RISK-...)")
    if not _RISK_MITIGATION_RE.search(content):
        issues.append("No Mitigation sections found")
    return issues


def _validate_fault_trees_content(filepath: str) -> list[str]:
    """Check fault trees have structural elements."""
    issues: list[str] = []
    try:
        content = open(filepath, encoding="utf-8").read()
    except OSError:
        return [f"Cannot read {filepath}"]

    if not _FTA_TOP_EVENT_RE.search(content):
        issues.append("No Top Event reference found (expected: Top Event or TE-N)")
    if not _FTA_STRUCTURE_RE.search(content):
        issues.append("No FTA structure found (expected: MCS, AND-Gate, OR-Gate, or Minimal Cut)")
    return issues


def _validate_stride_content(filepath: str) -> list[str]:
    """Check STRIDE threat model has review structure."""
    issues: list[str] = []
    try:
        content = open(filepath, encoding="utf-8").read()
    except OSError:
        return [f"Cannot read {filepath}"]

    if not _STRIDE_REVIEW_RE.search(content):
        issues.append("No 'STRIDE review:' section found")
    if not _STRIDE_ITEMS_RE.search(content):
        issues.append("No STRIDE item entries found (expected: S/T/R/I/D/E analysis)")
    return issues


def validate_audit_content() -> dict[str, list[str]]:
    """Validate structural integrity of all audit artifacts.

    Returns a dict mapping artifact path to list of issues (empty = valid).
    """
    validators = {
        "audit_results/fmea_matrix.md": _validate_fmea_content,
        "audit_results/risk_register.md": _validate_risk_register_content,
        "audit_results/fault_trees.md": _validate_fault_trees_content,
        "audit_results/stride_threat_model.md": _validate_stride_content,
    }
    results: dict[str, list[str]] = {}
    for path, validator in validators.items():
        issues = validator(path)
        if issues:
            results[path] = issues
    return results


def main() -> int:
    """Run the risk audit compliance check."""
    diff_base = None
    content_check = "--content-check" in sys.argv
    if "--diff-base" in sys.argv:
        idx = sys.argv.index("--diff-base")
        if idx + 1 < len(sys.argv):
            diff_base = sys.argv[idx + 1]

    # Gate 1: Audit artifacts must exist (non-deletion check)
    missing = _check_audit_artifacts_exist()
    if missing:
        print(">>> [risk-audit] ERROR: Required audit artifacts missing:")
        for m in missing:
            print(f">>>   - {m}")
        print(">>> [risk-audit] These files are protected by POLICY §18 and must not be deleted.")
        return 1

    # Gate 1b: Content validation (optional, enabled with --content-check)
    if content_check:
        content_issues = validate_audit_content()
        if content_issues:
            print(">>> [risk-audit] ERROR: Audit artifact content validation failed:")
            for artifact, issues in content_issues.items():
                print(f">>>   {artifact}:")
                for issue in issues:
                    print(f">>>     - {issue}")
            print(">>> [risk-audit]")
            print(">>> [risk-audit] Audit artifacts must contain structured content,")
            print(">>> [risk-audit] not just exist as files. See POLICY §18.")
            return 2

    # Gate 2: Signal changes require audit updates
    changed_files = _get_changed_files(diff_base)
    if not changed_files:
        print(">>> [risk-audit] OK: No changed files detected.")
        return 0

    signal_changes = [f for f in changed_files if _is_signal_change(f)]
    audit_changes = [f for f in changed_files if _is_audit_change(f)]

    if not signal_changes:
        print(">>> [risk-audit] OK: No signal/ingestion/output changes detected.")
        return 0

    if audit_changes:
        print(">>> [risk-audit] OK: Signal changes detected with matching audit updates.")
        print(f">>>   Signal changes: {len(signal_changes)} file(s)")
        print(f">>>   Audit updates:  {len(audit_changes)} file(s)")
        return 0

    # Signal changes without audit updates = violation
    print(">>> [risk-audit] ERROR: Signal/architecture changes detected without audit updates.")
    print(">>> [risk-audit]")
    print(">>> [risk-audit] Changed signal files:")
    for f in signal_changes:
        print(f">>>   - {f}")
    print(">>> [risk-audit]")
    print(">>> [risk-audit] POLICY §18 requires updating at least one of:")
    for a in AUDIT_ARTIFACTS:
        print(f">>>   - {a}")
    print(">>> [risk-audit]")
    print(">>> [risk-audit] Required actions per change type:")
    print(">>>   Signal change  → FMEA (FP+FN entry) + FTA check + Risk Register")
    print(">>>   Input/Output   → STRIDE (S/T/R/I/D/E) + Risk Register")
    print(">>>   Precision Δ>5% → FMEA (recalc RPNs) + Risk Register")
    print(">>> [risk-audit]")
    print(">>> [risk-audit] Push blocked until audit artifacts are updated.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
