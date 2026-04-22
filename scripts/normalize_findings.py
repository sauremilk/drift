#!/usr/bin/env python3
"""Normalize review findings into a machine-readable schema.

Accepts review notes in two formats:
1. Markdown bullet lists with `Key: value` lines under each bullet.
2. A raw JSON list of objects.

Emits a JSON array of normalized findings validated against
docs/schemas/finding_normalized.schema.json.

Pflichtfelder: severity, location, reproduction, proposed_action.
Fehlt ein Pflichtfeld, wird das Finding NICHT still ergaenzt — es wird
im Report als Fehler ausgewiesen und der Exit-Code ist != 0.

Usage:
    python scripts/normalize_findings.py --input review.md --output out.json
    python scripts/normalize_findings.py --input review.json --output out.json
    python scripts/normalize_findings.py --input review.md --output - | jq .
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

VALID_SEVERITIES = ("critical", "high", "medium", "low", "info")
REQUIRED_FIELDS = ("severity", "location", "reproduction", "proposed_action")
OPTIONAL_FIELDS = ("free_text", "id")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

_KEY_MAP = {
    "severity": "severity",
    "schweregrad": "severity",
    "location": "location",
    "ort": "location",
    "stelle": "location",
    "reproduction": "reproduction",
    "repro": "reproduction",
    "reproduktion": "reproduction",
    "proposed_action": "proposed_action",
    "action": "proposed_action",
    "massnahme": "proposed_action",
    "maßnahme": "proposed_action",
    "fix": "proposed_action",
    "free_text": "free_text",
    "freitext": "free_text",
    "notes": "free_text",
    "id": "id",
}


class NormalizationError(Exception):
    """Raised when a finding cannot be normalized deterministically."""


def _canonical_key(raw: str) -> str | None:
    return _KEY_MAP.get(raw.strip().lower().replace(" ", "_"))


def parse_markdown(text: str) -> list[dict[str, str]]:
    """Parse markdown bullet lists into flat finding dicts."""
    findings: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        # New bullet starts a new finding.
        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet_match:
            if current:
                findings.append(current)
            current = {}
            rest = bullet_match.group(1).strip()
            if ":" in rest:
                key_raw, value = rest.split(":", 1)
                canonical = _canonical_key(key_raw)
                if canonical:
                    current[canonical] = value.strip()
            continue

        # Continuation line: must contain Key: value.
        if current is None:
            continue
        indent_match = re.match(r"^\s+(.+)$", line)
        if not indent_match:
            continue
        content = indent_match.group(1).strip()
        if ":" not in content:
            continue
        key_raw, value = content.split(":", 1)
        canonical = _canonical_key(key_raw)
        if canonical:
            current[canonical] = value.strip()

    if current:
        findings.append(current)
    return findings


def parse_input(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise NormalizationError("JSON input must be a list of finding objects")
        return data
    return parse_markdown(text)  # type: ignore[return-value]


def validate_finding(finding: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []

    extra = set(finding) - set(ALL_FIELDS)
    for key in sorted(extra):
        errors.append(f"#{index}: unknown field {key!r}")

    for field in REQUIRED_FIELDS:
        value = finding.get(field)
        if value is None or not str(value).strip():
            errors.append(f"#{index}: missing required field {field!r}")

    severity = finding.get("severity")
    if severity is not None and severity not in VALID_SEVERITIES:
        errors.append(
            f"#{index}: severity must be one of {VALID_SEVERITIES}, got {severity!r}"
        )
    return errors


def normalize(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate findings; never silently fill missing fields."""
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            errors.append(f"#{index}: not an object ({type(finding).__name__})")
            continue
        finding_errors = validate_finding(finding, index)
        if finding_errors:
            errors.extend(finding_errors)
            continue
        # Assign deterministic id if missing (non-sensitive, based on content).
        entry = {k: str(v) for k, v in finding.items() if k in ALL_FIELDS}
        if "id" not in entry:
            entry["id"] = f"f{index:03d}"
        normalized.append(entry)
    return normalized, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize review findings into a JSON schema.")
    parser.add_argument("--input", required=True, help="Path to markdown or JSON review file.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON file (use '-' for stdout).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 2

    try:
        raw = parse_input(input_path)
    except (OSError, json.JSONDecodeError, NormalizationError) as exc:
        print(f"error: failed to parse input: {exc}", file=sys.stderr)
        return 2

    normalized, errors = normalize(raw)
    if errors:
        print("Normalization errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    payload = json.dumps(normalized, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
