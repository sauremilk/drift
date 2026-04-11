#!/usr/bin/env python3
"""Generate drift.output.schema.json from the code-defined output structure.

Usage:
    python scripts/generate_output_schema.py [--output drift.output.schema.json]

This script produces a JSON Schema (draft-07) that describes the structure of
``drift analyze --format json`` output.  It is used for agent-side validation
and documentation purposes.

The generated schema is checked in CI to detect unintentional output-format
drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema definition (manually derived from json_output.py + models.py)
# ---------------------------------------------------------------------------
from drift.models import OUTPUT_SCHEMA_VERSION

_SEVERITY_ENUM = ["critical", "high", "medium", "low", "info"]
_STATUS_ENUM = ["active", "suppressed", "resolved"]

_LOGICAL_LOCATION = {
    "type": ["object", "null"],
    "properties": {
        "fully_qualified_name": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "kind": {"type": ["string", "null"]},
        "class_name": {"type": ["string", "null"]},
        "namespace": {"type": ["string", "null"]},
    },
}

_ATTRIBUTION = {
    "type": ["object", "null"],
    "properties": {
        "commit_hash": {"type": "string"},
        "author": {"type": "string"},
        "email": {"type": "string"},
        "date": {"type": "string", "format": "date"},
        "branch_hint": {"type": ["string", "null"]},
        "ai_attributed": {"type": "boolean"},
        "ai_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "commit_message": {"type": "string"},
    },
}

_REMEDIATION = {
    "type": ["object", "null"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "effort": {"type": "string"},
        "impact": {"type": "string"},
    },
}

_FINDING_COMPACT = {
    "type": "object",
    "required": ["rank", "finding_id", "signal", "severity", "title"],
    "properties": {
        "rank": {"type": "integer", "minimum": 1},
        "finding_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{16}$",
            "description": "Deterministic content-based fingerprint (SHA256 prefix).",
        },
        "signal": {"type": "string"},
        "signal_abbrev": {"type": "string"},
        "rule_id": {"type": ["string", "null"]},
        "severity": {"type": "string", "enum": _SEVERITY_ENUM},
        "status": {"type": "string", "enum": _STATUS_ENUM},
        "finding_context": {"type": "string"},
        "impact": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "score_contribution": {"type": "number"},
        "title": {"type": "string"},
        "file": {"type": ["string", "null"]},
        "start_line": {"type": ["integer", "null"]},
        "duplicate_count": {"type": "integer", "minimum": 1},
        "next_step": {"type": ["string", "null"]},
    },
}

_FINDING_FULL = {
    "type": "object",
    "required": ["finding_id", "signal", "severity", "title"],
    "properties": {
        "finding_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{16}$",
            "description": "Deterministic content-based fingerprint (SHA256 prefix).",
        },
        "signal": {"type": "string"},
        "signal_abbrev": {"type": "string"},
        "rule_id": {"type": ["string", "null"]},
        "severity": {"type": "string", "enum": _SEVERITY_ENUM},
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "impact": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "score_contribution": {"type": "number"},
        "impact_rank": {"type": ["integer", "null"]},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "fix": {"type": ["string", "null"]},
        "file": {"type": ["string", "null"]},
        "start_line": {"type": ["integer", "null"]},
        "end_line": {"type": ["integer", "null"]},
        "finding_context": {"type": "string"},
        "symbol": {"type": ["string", "null"]},
        "logical_location": _LOGICAL_LOCATION,
        "related_files": {"type": "array", "items": {"type": "string"}},
        "ai_attributed": {"type": "boolean"},
        "deferred": {"type": "boolean"},
        "status": {"type": "string", "enum": _STATUS_ENUM},
        "status_set_by": {"type": ["string", "null"]},
        "status_reason": {"type": ["string", "null"]},
        "metadata": {"type": "object"},
        "attribution": _ATTRIBUTION,
        "remediation": _REMEDIATION,
    },
}

_FIX_FIRST_ITEM = {
    "type": "object",
    "required": ["rank", "finding_id", "signal", "severity", "title"],
    "properties": {
        "rank": {"type": "integer", "minimum": 1},
        "finding_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{16}$",
        },
        "priority_class": {"type": "string"},
        "signal": {"type": "string"},
        "signal_abbrev": {"type": "string"},
        "rule_id": {"type": ["string", "null"]},
        "severity": {"type": "string", "enum": _SEVERITY_ENUM},
        "finding_context": {"type": "string"},
        "impact": {"type": "number"},
        "score_contribution": {"type": "number"},
        "title": {"type": "string"},
        "file": {"type": ["string", "null"]},
        "start_line": {"type": ["integer", "null"]},
        "next_step": {"type": ["string", "null"]},
        "expected_benefit": {"type": "string"},
    },
}

_MODULE = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "drift_score": {"type": "number"},
        "severity": {"type": "string", "enum": _SEVERITY_ENUM},
        "signal_scores": {"type": "object", "additionalProperties": {"type": "number"}},
        "finding_count": {"type": "integer"},
        "ai_ratio": {"type": "number"},
    },
}

_TREND = {
    "type": ["object", "null"],
    "properties": {
        "previous_score": {"type": ["number", "null"]},
        "delta": {"type": ["number", "null"]},
        "direction": {"type": "string"},
        "recent_scores": {"type": "array", "items": {"type": "number"}},
        "history_depth": {"type": "integer"},
        "transition_ratio": {"type": ["number", "null"]},
    },
}


def build_output_schema() -> dict:
    """Build the complete JSON Schema for drift CLI JSON output."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://drift-analyzer.dev/schemas/output/v{OUTPUT_SCHEMA_VERSION}",
        "title": "Drift Analysis Output",
        "description": (
            f"JSON output schema for 'drift analyze --format json' (v{OUTPUT_SCHEMA_VERSION}). "
            "Major version = breaking changes, minor version = additive fields."
        ),
        "type": "object",
        "required": [
            "schema_version",
            "version",
            "repo",
            "analyzed_at",
            "drift_score",
            "severity",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": OUTPUT_SCHEMA_VERSION,
                "description": "Output format version (semver-like: major.minor).",
            },
            "version": {
                "type": "string",
                "description": "Drift application version.",
            },
            "signal_abbrev_map": {
                "type": "object",
                "description": "Mapping of signal abbreviations to canonical signal type names.",
                "additionalProperties": {"type": "string"},
            },
            "repo": {"type": "string"},
            "analyzed_at": {"type": "string", "format": "date-time"},
            "drift_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "drift_score_scope": {"type": "string"},
            "severity": {"type": "string", "enum": _SEVERITY_ENUM},
            "analysis_status": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "degraded": {"type": "boolean"},
                    "is_fully_reliable": {"type": "boolean"},
                    "causes": {"type": "array", "items": {"type": "string"}},
                    "affected_components": {"type": "array", "items": {"type": "string"}},
                    "events": {"type": "array"},
                },
            },
            "trend": _TREND,
            "summary": {
                "type": "object",
                "properties": {
                    "total_files": {"type": "integer"},
                    "total_functions": {"type": "integer"},
                    "ai_attributed_ratio": {"type": "number"},
                    "ai_tools_detected": {"type": "array", "items": {"type": "string"}},
                    "analysis_duration_seconds": {"type": ["number", "null"]},
                },
            },
            "findings_compact": {
                "type": "array",
                "items": _FINDING_COMPACT,
                "description": "Ranked findings in compact form for quick prioritization.",
            },
            "compact_summary": {
                "type": "object",
                "properties": {
                    "findings_total": {"type": "integer"},
                    "findings_deduplicated": {"type": "integer"},
                    "duplicate_findings_removed": {"type": "integer"},
                    "suppressed_total": {"type": "integer"},
                    "critical_count": {"type": "integer"},
                    "high_count": {"type": "integer"},
                    "fix_first_count": {"type": "integer"},
                },
            },
            "fix_first": {
                "type": "array",
                "items": _FIX_FIRST_ITEM,
                "description": "Top prioritized findings for immediate action.",
            },
            "finding_context_policy": {"type": "object"},
            "suppressed_count": {"type": "integer"},
            "context_tagged_count": {"type": "integer"},
            "baseline": {
                "type": ["object", "null"],
                "properties": {
                    "applied": {"type": "boolean"},
                    "new_findings_count": {"type": ["integer", "null"]},
                    "baseline_matched_count": {"type": ["integer", "null"]},
                },
            },
            "negative_context": {"type": "array"},
            "modules": {
                "type": "array",
                "items": _MODULE,
                "description": "Per-module drift scores (omitted in compact mode).",
            },
            "findings": {
                "type": "array",
                "items": _FINDING_FULL,
                "description": "Full finding details (omitted in compact mode).",
            },
            "findings_suppressed": {
                "type": "array",
                "items": _FINDING_FULL,
                "description": "Suppressed findings (omitted in compact mode).",
            },
        },
        "additionalProperties": True,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate drift output JSON schema.")
    parser.add_argument(
        "--output", "-o",
        default="drift.output.schema.json",
        help="Output file path (default: drift.output.schema.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that the existing schema matches the generated one.",
    )
    args = parser.parse_args()

    schema = build_output_schema()
    schema_json = json.dumps(schema, indent=2, sort_keys=False) + "\n"

    if args.check:
        target = Path(args.output)
        if not target.exists():
            print(f"FAIL: {target} does not exist", file=sys.stderr)
            sys.exit(1)
        existing = target.read_text(encoding="utf-8")
        if existing != schema_json:
            print(
                f"FAIL: {target} is out of date. Run:\n"
                f"  python scripts/generate_output_schema.py -o {target}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK: {target} is up to date.")
        return

    out_path = Path(args.output)
    out_path.write_text(schema_json, encoding="utf-8")
    print(f"Wrote {out_path} (schema_version={OUTPUT_SCHEMA_VERSION})")


if __name__ == "__main__":
    main()
