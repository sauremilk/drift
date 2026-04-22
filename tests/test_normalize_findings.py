"""Tests for scripts/normalize_findings.py — parse, validate, error-report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import normalize_findings as nf  # noqa: E402

VALID_MD = """\
- Severity: high
  Location: src/drift/cli.py:42
  Reproduction: run drift analyze on fixture X
  Proposed_Action: guard empty-result path with explicit branch

- severity: low
  location: docs/README.md
  reproduction: manual visual review
  proposed_action: rewrite sentence for clarity
  free_text: minor nitpick
"""


def test_parse_markdown_basic() -> None:
    findings = nf.parse_markdown(VALID_MD)
    assert len(findings) == 2
    assert findings[0]["severity"] == "high"
    assert findings[0]["location"] == "src/drift/cli.py:42"
    assert findings[1]["free_text"] == "minor nitpick"


def test_normalize_assigns_ids() -> None:
    findings = nf.parse_markdown(VALID_MD)
    normalized, errors = nf.normalize(findings)
    assert errors == []
    assert len(normalized) == 2
    assert normalized[0]["id"] == "f001"
    assert normalized[1]["id"] == "f002"


def test_missing_required_field_produces_error() -> None:
    incomplete = [
        {"severity": "high", "location": "x", "reproduction": "y"},  # missing proposed_action
    ]
    normalized, errors = nf.normalize(incomplete)
    assert normalized == []
    assert errors
    assert "proposed_action" in errors[0]


def test_invalid_severity_rejected() -> None:
    bad = [
        {
            "severity": "CATASTROPHIC",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
        }
    ]
    _, errors = nf.normalize(bad)
    assert errors
    assert "severity" in errors[0]


def test_empty_string_counts_as_missing() -> None:
    bad = [
        {
            "severity": "high",
            "location": "   ",
            "reproduction": "y",
            "proposed_action": "z",
        }
    ]
    _, errors = nf.normalize(bad)
    assert errors


def test_unknown_field_reported() -> None:
    weird = [
        {
            "severity": "low",
            "location": "x",
            "reproduction": "y",
            "proposed_action": "z",
            "vibes": "off",
        }
    ]
    _, errors = nf.normalize(weird)
    assert any("vibes" in e for e in errors)


def test_cli_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    in_path = tmp_path / "review.md"
    out_path = tmp_path / "out.json"
    in_path.write_text(VALID_MD, encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["normalize_findings.py", "--input", str(in_path), "--output", str(out_path)],
    )
    exit_code = nf.main()
    assert exit_code == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(payload) == 2
    assert payload[0]["severity"] == "high"


def test_cli_exit_nonzero_on_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    in_path = tmp_path / "review.md"
    out_path = tmp_path / "out.json"
    in_path.write_text("- Severity: high\n  Location: x\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["normalize_findings.py", "--input", str(in_path), "--output", str(out_path)],
    )
    exit_code = nf.main()
    assert exit_code == 1


def test_json_input_parses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    in_path = tmp_path / "review.json"
    out_path = tmp_path / "out.json"
    in_path.write_text(
        json.dumps(
            [
                {
                    "severity": "medium",
                    "location": "x.py",
                    "reproduction": "pytest",
                    "proposed_action": "fix",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["normalize_findings.py", "--input", str(in_path), "--output", str(out_path)],
    )
    assert nf.main() == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload[0]["severity"] == "medium"


def test_schema_file_exists_and_matches_fields() -> None:
    schema_path = REPO_ROOT / "docs" / "schemas" / "finding_normalized.schema.json"
    assert schema_path.is_file()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["required"]) == set(nf.REQUIRED_FIELDS)
    enum = schema["properties"]["severity"]["enum"]
    assert set(enum) == set(nf.VALID_SEVERITIES)
