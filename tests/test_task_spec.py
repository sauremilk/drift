"""Tests for the Task Specification model (M1) and validation script."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from drift.task_spec import ArchitectureLayer, TaskSpec, validate_task_spec

# ── TaskSpec model tests ───────────────────────────────────────────

class TestTaskSpecModel:
    """Core model construction and auto-inference."""

    def test_minimal_valid_spec(self):
        spec = TaskSpec(
            goal="Extend audit content validation logic",
            affected_layers=[ArchitectureLayer.SCRIPTS],
            acceptance_criteria=["All audit artifacts pass content check"],
        )
        assert spec.requires_adr is False
        assert spec.requires_audit_update is False

    def test_signal_layer_auto_inference(self):
        spec = TaskSpec(
            goal="Add new code clone detection signal",
            affected_layers=[ArchitectureLayer.SIGNALS],
            acceptance_criteria=["Signal detects clones with >80% precision"],
        )
        assert spec.requires_adr is True
        assert spec.requires_audit_update is True

    def test_output_layer_auto_inference(self):
        spec = TaskSpec(
            goal="Add CSV output format",
            affected_layers=[ArchitectureLayer.OUTPUT],
            acceptance_criteria=["CSV export works for all finding types"],
        )
        assert spec.requires_adr is True
        assert spec.requires_audit_update is True

    def test_ingestion_layer_auto_inference(self):
        spec = TaskSpec(
            goal="Improve git history parsing performance",
            affected_layers=[ArchitectureLayer.INGESTION],
            acceptance_criteria=["Git history parsed 2x faster"],
        )
        # ingestion triggers audit but not necessarily ADR
        assert spec.requires_audit_update is True

    def test_explicit_override_preserves_values(self):
        spec = TaskSpec(
            goal="Refactor scoring weights with ADR approval",
            affected_layers=[ArchitectureLayer.SCORING],
            acceptance_criteria=["Weights updated per ADR-034"],
            requires_adr=True,
            requires_audit_update=False,
        )
        assert spec.requires_adr is True
        assert spec.requires_audit_update is False

    def test_multiple_layers(self):
        spec = TaskSpec(
            goal="End-to-end feature spanning signals and output",
            affected_layers=[
                ArchitectureLayer.SIGNALS,
                ArchitectureLayer.OUTPUT,
                ArchitectureLayer.TESTS,
            ],
            acceptance_criteria=["All integration tests pass"],
        )
        assert spec.requires_adr is True
        assert spec.requires_audit_update is True

    def test_commit_type_default(self):
        spec = TaskSpec(
            goal="Simple documentation fix",
            affected_layers=[ArchitectureLayer.DOCS],
            acceptance_criteria=["Docs updated correctly"],
        )
        assert spec.commit_type == ""

    def test_all_architecture_layers_exist(self):
        expected = {
            "signals", "ingestion", "scoring", "output", "commands",
            "config", "plugins", "tests", "scripts", "docs", "prompts",
        }
        assert {layer.value for layer in ArchitectureLayer} == expected


# ── validate_task_spec tests ───────────────────────────────────────

class TestValidateTaskSpec:
    """Semantic validation beyond schema."""

    def test_valid_spec_advisory_only(self):
        spec = TaskSpec(
            goal="Extend audit content validation logic",
            affected_layers=[ArchitectureLayer.SCRIPTS],
            acceptance_criteria=["All audit artifacts pass content check"],
        )
        issues = validate_task_spec(spec)
        # Advisory issues (scope_boundaries) are acceptable
        assert all("scope_boundaries" in i or "advisory" in i.lower() for i in issues)

    def test_missing_tests_layer_warning(self):
        spec = TaskSpec(
            goal="Add new signal for dead imports",
            affected_layers=[ArchitectureLayer.SIGNALS],
            acceptance_criteria=["Signal detects dead imports"],
        )
        issues = validate_task_spec(spec)
        # Should warn about missing tests layer
        assert any("tests" in i.lower() for i in issues)

    def test_adr_required_but_missing(self):
        spec = TaskSpec(
            goal="Change scoring weights",
            affected_layers=[ArchitectureLayer.SCORING, ArchitectureLayer.TESTS],
            acceptance_criteria=["Score regression tests pass"],
            requires_adr=True,
        )
        issues = validate_task_spec(spec)
        # Not necessarily an error (ADR may exist), but may warn
        # Just check it doesn't crash
        assert isinstance(issues, list)

    def test_vague_acceptance_criteria_warning(self):
        spec = TaskSpec(
            goal="Improve drift analysis quality significantly",
            affected_layers=[ArchitectureLayer.SIGNALS, ArchitectureLayer.TESTS],
            acceptance_criteria=["works"],  # Too vague
        )
        issues = validate_task_spec(spec)
        assert any("short" in i.lower() or "vague" in i.lower() for i in issues)

    def test_forbidden_path_tagesplanung(self):
        spec = TaskSpec(
            goal="Update daily planning document",
            affected_layers=[ArchitectureLayer.DOCS],
            acceptance_criteria=["Planning updated"],
            forbidden_paths=["tagesplanung/"],
        )
        issues = validate_task_spec(spec)
        assert isinstance(issues, list)  # Valid construction


# ── YAML/JSON serialization round-trip ─────────────────────────────

class TestTaskSpecSerialization:
    """Ensure specs can be saved and reloaded."""

    def test_yaml_roundtrip(self, tmp_path: Path):
        spec = TaskSpec(
            goal="Add CSV output format for findings",
            affected_layers=[ArchitectureLayer.OUTPUT, ArchitectureLayer.TESTS],
            acceptance_criteria=["CSV matches JSON content", "Header row present"],
            commit_type="feat",
        )
        yaml_path = tmp_path / "task.yaml"
        yaml_path.write_text(
            yaml.dump(json.loads(spec.model_dump_json()), default_flow_style=False),
            encoding="utf-8",
        )

        reloaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        spec2 = TaskSpec(**reloaded)
        assert spec2.goal == spec.goal
        assert set(spec2.affected_layers) == set(spec.affected_layers)
        assert spec2.requires_adr == spec.requires_adr

    def test_json_roundtrip(self, tmp_path: Path):
        spec = TaskSpec(
            goal="Refactor ingestion pipeline for parallelism",
            affected_layers=[ArchitectureLayer.INGESTION],
            acceptance_criteria=["Parallel ingestion 3x faster"],
        )
        json_path = tmp_path / "task.json"
        json_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

        reloaded = json.loads(json_path.read_text(encoding="utf-8"))
        spec2 = TaskSpec(**reloaded)
        assert spec2.requires_audit_update is True


# ── validate_task_spec.py CLI tests ────────────────────────────────

class TestValidateTaskSpecCLI:
    """Test the CLI script via subprocess."""

    def test_example_flag(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, "scripts/validate_task_spec.py", "--example"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        # Output should be valid YAML
        parsed = yaml.safe_load(result.stdout)
        assert "goal" in parsed
        assert "affected_layers" in parsed

    def test_valid_yaml_file(self, tmp_path: Path):
        import subprocess

        spec_data = {
            "goal": "Fix false positive in MDS signal for test helpers",
            "affected_layers": ["signals", "tests"],
            "acceptance_criteria": ["MDS no longer flags test helpers", "No recall regression"],
            "commit_type": "fix",
        }
        yaml_path = tmp_path / "task.yaml"
        yaml_path.write_text(yaml.dump(spec_data), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "scripts/validate_task_spec.py", str(yaml_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0

    def test_invalid_yaml_file(self, tmp_path: Path):
        import subprocess

        bad_data = {"goal": "x", "affected_layers": []}
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text(yaml.dump(bad_data), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "scripts/validate_task_spec.py", str(yaml_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 1
