"""Regression tests for issue #454: summary.phase_timing schema contract."""

from __future__ import annotations

import json
from pathlib import Path


def test_output_schema_declares_summary_phase_timing() -> None:
    schema = json.loads(Path("drift.output.schema.json").read_text(encoding="utf-8"))

    summary_properties = schema["properties"]["summary"]["properties"]
    assert "phase_timing" in summary_properties
