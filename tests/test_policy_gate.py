"""Tests for check_policy_gate.py (M2 — Runtime Policy Gate Logic)."""

from __future__ import annotations

# Dynamic import since scripts/ is not a package
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_policy_gate",
    Path(__file__).resolve().parent.parent / "scripts" / "check_policy_gate.py",
)
assert _spec and _spec.loader
check_policy_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_policy_gate)  # type: ignore[union-attr]

validate_gate = check_policy_gate.validate_gate


class TestValidateGate:
    """Core policy gate validation logic."""

    def test_valid_gate_no_issues(self, tmp_path: Path):
        gate = {
            "aufgabe": "Extend audit validation with content checks",
            "zulassungskriterium": "JA → Glaubwürdigkeit",
            "entscheidung": "ZULÄSSIG",
            "betrifft_signal_architektur": "NEIN",
            "begründung": "Stärkt Nachvollziehbarkeit der Audit-Artefakte",
        }
        issues = validate_gate(gate, tmp_path)
        assert issues == []

    def test_missing_aufgabe(self, tmp_path: Path):
        gate = {
            "entscheidung": "ZULÄSSIG",
            "begründung": "Some valid reasoning here",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("aufgabe" in i.lower() for i in issues)

    def test_missing_entscheidung(self, tmp_path: Path):
        gate = {
            "aufgabe": "Some task description longer than ten",
            "begründung": "Some valid reasoning here",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("entscheidung" in i.lower() for i in issues)

    def test_invalid_entscheidung_value(self, tmp_path: Path):
        gate = {
            "aufgabe": "Some task that is well described",
            "entscheidung": "VIELLEICHT",
            "begründung": "Unclear whether this is allowed",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("ZULÄSSIG" in i or "ABBRUCH" in i for i in issues)

    def test_short_begruendung_warning(self, tmp_path: Path):
        gate = {
            "aufgabe": "Fix a bug in the scoring module",
            "entscheidung": "ZULÄSSIG",
            "begründung": "ok",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("ritualistic" in i.lower() or "short" in i.lower() for i in issues)

    def test_inconsistent_signal_layers(self, tmp_path: Path):
        gate = {
            "aufgabe": "Add new signal for detecting circular imports",
            "entscheidung": "ZULÄSSIG",
            "betrifft_signal_architektur": "NEIN",
            "affected_layers": "signals,scoring",
            "begründung": "New signal to detect circular import patterns",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("inconsistent" in i.lower() for i in issues)

    def test_consistent_signal_layers_ja(self, tmp_path: Path):
        # Create audit artifacts so the existence check passes
        (tmp_path / "audit_results").mkdir()
        for artifact in check_policy_gate.AUDIT_ARTIFACTS:
            (tmp_path / artifact).write_text("content", encoding="utf-8")
        # Create decisions dir with an ADR
        (tmp_path / "decisions").mkdir()
        (tmp_path / "decisions" / "ADR-001.md").write_text("# ADR", encoding="utf-8")

        gate = {
            "aufgabe": "Add new signal for detecting circular imports",
            "entscheidung": "ZULÄSSIG",
            "betrifft_signal_architektur": "JA",
            "affected_layers": "signals,tests",
            "begründung": "New signal to detect circular import patterns reliably",
        }
        issues = validate_gate(gate, tmp_path)
        assert not any("inconsistent" in i.lower() for i in issues)

    def test_abbruch_is_valid_decision(self, tmp_path: Path):
        gate = {
            "aufgabe": "Task that violates exclusion criteria clearly",
            "entscheidung": "ABBRUCH",
            "begründung": "Erzeugt mehr Komplexität ohne klaren Nutzen",
        }
        issues = validate_gate(gate, tmp_path)
        assert not any("entscheidung" in i.lower() for i in issues)

    def test_missing_audit_artifacts_when_signal_work(self, tmp_path: Path):
        gate = {
            "aufgabe": "Modify ingestion pipeline for new file types",
            "entscheidung": "ZULÄSSIG",
            "betrifft_signal_architektur": "JA",
            "begründung": "Extends file discovery to support .vue files",
        }
        issues = validate_gate(gate, tmp_path)
        assert any("audit artifact missing" in i.lower() for i in issues)
