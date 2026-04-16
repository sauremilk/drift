"""Regression test for Issue #383.

Bug: ``drift.schema.json`` defined ``ThresholdsConfig`` with
``additionalProperties: false`` and no ``guided`` property, while the
runtime injected a ``thresholds.guided`` key. This caused schema-runtime
incompatibility: IDE validators flagged ``guided_thresholds`` as invalid,
and ``extends: vibe-coding`` crashed at runtime (see #382).

Fix: ``GuidedThresholds`` is a dedicated sub-model and ``guided_thresholds``
is a first-class top-level field on ``DriftConfig``. The committed
``drift.schema.json`` must reflect this.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "drift.schema.json"


class TestIssue383SchemaGuidedThresholds:
    """drift.schema.json must include GuidedThresholds and guided_thresholds."""

    def test_schema_contains_guided_thresholds_definition(self) -> None:
        """``$defs.GuidedThresholds`` must exist in the committed schema."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert "GuidedThresholds" in schema.get("$defs", {}), (
            "drift.schema.json is missing $defs.GuidedThresholds. "
            "Regenerate with: drift config schema --output drift.schema.json"
        )

    def test_schema_guided_thresholds_has_required_properties(self) -> None:
        """GuidedThresholds must define green_max and yellow_max."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        guided_def = schema["$defs"]["GuidedThresholds"]
        properties = guided_def.get("properties", {})
        assert "green_max" in properties, "GuidedThresholds.green_max missing from schema"
        assert "yellow_max" in properties, "GuidedThresholds.yellow_max missing from schema"

    def test_schema_top_level_has_guided_thresholds_field(self) -> None:
        """``guided_thresholds`` must appear as a top-level property in the schema."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        properties = schema.get("properties", {})
        assert "guided_thresholds" in properties, (
            "drift.schema.json is missing top-level 'guided_thresholds' property. "
            "Regenerate with: drift config schema --output drift.schema.json"
        )

    def test_thresholds_config_has_no_guided_property(self) -> None:
        """``ThresholdsConfig`` must NOT have a ``guided`` property (extra=forbid)."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        thresholds_def = schema.get("$defs", {}).get("ThresholdsConfig", {})
        properties = thresholds_def.get("properties", {})
        assert "guided" not in properties, (
            "ThresholdsConfig must not have a 'guided' property; "
            "guided_thresholds is a top-level DriftConfig field."
        )

    def test_schema_matches_live_model(self) -> None:
        """Committed drift.schema.json must match build_config_json_schema() output."""
        from drift.config import build_config_json_schema

        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        expected = build_config_json_schema()
        assert committed == expected, (
            "drift.schema.json is out of sync with DriftConfig. "
            "Regenerate with: drift config schema --output drift.schema.json"
        )
