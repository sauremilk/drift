"""Phase 2 — Contract Formalization.

Links each contract to a verifiable Drift signal and validates the
contract set against the intent JSON schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drift.intent.models import Contract

# ---------------------------------------------------------------------------
# Contract category → Drift signal mapping
# ---------------------------------------------------------------------------

_CATEGORY_SIGNAL_MAP: dict[str, str] = {
    "persistence": "exception_contract_drift",
    "security": "missing_authorization",
    "error_handling": "broad_exception_monoculture",
    "communication": "exception_contract_drift",
    "automation": "broad_exception_monoculture",
    "utility": "guard_clause_deficit",
}

# More granular mapping by contract ID prefix
_CONTRACT_SIGNAL_MAP: dict[str, str] = {
    "persist-survive-restart": "exception_contract_drift",
    "persist-concurrent-safety": "exception_contract_drift",
    "persist-input-integrity": "guard_clause_deficit",
    "sec-no-plaintext-secrets": "hardcoded_secret_candidate",
    "sec-input-validation": "guard_clause_deficit",
    "sec-external-data-validation": "guard_clause_deficit",
    "err-user-friendly-messages": "broad_exception_monoculture",
    "err-empty-input-resilience": "guard_clause_deficit",
    "err-network-data-safety": "broad_exception_monoculture",
}


def _resolve_signal(contract: Contract) -> str:
    """Resolve the verification signal for a contract.

    Order: contract-specific ID → category default → 'manual'.
    """
    # Check contract-specific mapping first
    signal = _CONTRACT_SIGNAL_MAP.get(contract.id)
    if signal:
        return signal

    # Fall back to category mapping
    signal = _CATEGORY_SIGNAL_MAP.get(contract.category)
    if signal:
        return signal

    return "manual"


def _load_schema() -> dict[str, Any]:
    """Load the intent JSON schema from package data."""
    schema_path = Path(__file__).parent / "schemas" / "intent.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _validate_against_schema(data: dict[str, Any]) -> list[str]:
    """Validate data against the intent JSON schema.

    Returns a list of error messages (empty if valid).
    Uses a lightweight check without requiring jsonschema as dependency.
    """
    errors: list[str] = []

    # Required top-level fields
    for field in ("schema_version", "prompt", "category", "contracts"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate contracts
    contracts = data.get("contracts", [])
    if not isinstance(contracts, list):
        errors.append("'contracts' must be a list")
        return errors

    if len(contracts) < 1:
        errors.append("At least one contract is required")

    valid_categories = {  # noqa: E501
        "persistence", "security", "error_handling", "communication", "automation", "utility",
    }
    valid_severities = {"critical", "high", "medium"}
    valid_sources = {"baseline", "extracted", "clarification"}

    for i, c in enumerate(contracts):
        prefix = f"contracts[{i}]"
        for req_field in (
            "id", "description_technical", "description_human",
            "category", "severity", "auto_repair_eligible", "source",
        ):
            if req_field not in c:
                errors.append(f"{prefix}: missing required field '{req_field}'")

        if c.get("category") not in valid_categories:
            errors.append(f"{prefix}: invalid category '{c.get('category')}'")

        if c.get("severity") not in valid_severities:
            errors.append(f"{prefix}: invalid severity '{c.get('severity')}'")

        if c.get("source") not in valid_sources:
            errors.append(f"{prefix}: invalid source '{c.get('source')}'")

    return errors


def formalize(
    intent_data: dict[str, Any],
) -> dict[str, Any]:
    """Execute Phase 2 — Contract Formalization.

    Parameters
    ----------
    intent_data:
        The ``drift.intent.json`` payload from Phase 1.

    Returns
    -------
    dict
        Updated intent data with verification_signal on each contract
        and a ``validation`` block.
    """
    contracts = intent_data.get("contracts", [])
    manual_count = 0
    total = len(contracts)

    for c_data in contracts:
        contract = Contract.from_dict(c_data)
        signal = _resolve_signal(contract)
        c_data["verification_signal"] = signal
        if signal == "manual":
            manual_count += 1

    # Schema validation
    validation_errors = _validate_against_schema(intent_data)

    # Manual signal warning
    warnings: list[str] = []
    if total > 0 and manual_count / total > 0.2:
        warnings.append(
            f"{manual_count}/{total} contracts have verification_signal='manual' "
            f"(>{int(0.2 * 100)}% threshold). Manual review recommended."
        )

    intent_data["validation"] = {
        "schema_valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": warnings,
        "manual_signal_count": manual_count,
        "total_contracts": total,
    }

    return intent_data
