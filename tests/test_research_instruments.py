"""Tests for the H1–H5 research instrument scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# ---------------------------------------------------------------------------
# Helpers — import script functions by path
# ---------------------------------------------------------------------------


def _import_annotation_sheet():
    """Import the annotation_sheet module."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import importlib

        spec = importlib.util.spec_from_file_location(
            "generate_annotation_sheet",
            SCRIPTS_DIR / "generate_annotation_sheet.py",
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    finally:
        sys.path.pop(0)


def _import_mutation_gap():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import importlib

        spec = importlib.util.spec_from_file_location(
            "mutation_gap_report",
            SCRIPTS_DIR / "mutation_gap_report.py",
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    finally:
        sys.path.pop(0)


# ---------------------------------------------------------------------------
# H1: Cohen's Kappa
# ---------------------------------------------------------------------------


class TestCohensKappa:
    """Unit tests for _cohens_kappa()."""

    def setup_method(self):
        self.mod = _import_annotation_sheet()

    def test_perfect_agreement(self):
        labels = ["TP", "FP", "TP", "DISPUTED", "FP"]
        assert self.mod._cohens_kappa(labels, labels) == pytest.approx(1.0)

    def test_no_agreement_beyond_chance(self):
        a = ["TP", "FP", "TP", "FP"]
        b = ["FP", "TP", "FP", "TP"]
        # Systematic disagreement — kappa should be negative or near 0
        kappa = self.mod._cohens_kappa(a, b)
        assert kappa < 0.3

    def test_moderate_agreement(self):
        a = ["TP", "TP", "FP", "FP", "TP", "DISPUTED", "TP", "FP", "TP", "TP"]
        b = ["TP", "TP", "FP", "TP", "TP", "DISPUTED", "TP", "FP", "FP", "TP"]
        kappa = self.mod._cohens_kappa(a, b)
        assert 0.3 < kappa < 0.9

    def test_empty_labels(self):
        import math

        kappa = self.mod._cohens_kappa([], [])
        assert math.isnan(kappa)

    def test_unequal_length_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            self.mod._cohens_kappa(["TP"], ["TP", "FP"])


class TestCompare:
    """Integration test for the compare() function."""

    def test_compare_writes_artifact(self, tmp_path):
        mod = _import_annotation_sheet()

        rater1 = [
            {"id": "f1", "signal": "PFS", "label": "TP"},
            {"id": "f2", "signal": "PFS", "label": "FP"},
            {"id": "f3", "signal": "MDS", "label": "TP"},
        ]
        rater2 = [
            {"id": "f1", "signal": "PFS", "label": "TP"},
            {"id": "f2", "signal": "PFS", "label": "TP"},
            {"id": "f3", "signal": "MDS", "label": "TP"},
        ]

        f1 = tmp_path / "rater1.json"
        f2 = tmp_path / "rater2.json"
        f1.write_text(json.dumps(rater1), encoding="utf-8")
        f2.write_text(json.dumps(rater2), encoding="utf-8")

        # Patch the output directory
        with patch.object(mod, "RESULTS_DIR", tmp_path):
            mod.compare(str(f1), str(f2))

        out = tmp_path / "annotation_agreement.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "kappa_overall" in data
        assert data["n_paired"] == 3


# ---------------------------------------------------------------------------
# H3: Mutation gap report helpers
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    """Unit tests for the title normalization in mutation_gap_report."""

    def setup_method(self):
        self.mod = _import_mutation_gap()

    def test_strips_file_paths(self):
        title = "Pattern fragmentation in src/drift/signals/foo.py"
        normalized = self.mod._normalize_title(title)
        assert "src/drift" not in normalized.lower()

    def test_collapses_whitespace(self):
        title = "Duplicate   logic  detected"
        normalized = self.mod._normalize_title(title)
        assert "  " not in normalized


class TestClusterFindings:
    """Test that findings are clustered by (signal, normalized_title)."""

    def setup_method(self):
        self.mod = _import_mutation_gap()

    def test_cluster_groups_by_signal(self):
        findings = [
            {"signal": "PFS", "title": "Fragmentation A"},
            {"signal": "PFS", "title": "Fragmentation B"},
            {"signal": "MDS", "title": "Module drift"},
        ]
        clusters = self.mod._cluster_findings(findings)
        assert "PFS" in clusters
        assert "MDS" in clusters
        # PFS has at least one pattern cluster
        assert len(clusters["PFS"]) >= 1
        assert len(clusters["MDS"]) >= 1


# ---------------------------------------------------------------------------
# H5: Adversarial manifest validation
# ---------------------------------------------------------------------------


class TestAdversarialManifest:
    """Validate the adversarial fixture manifest."""

    @pytest.fixture()
    def manifest(self):
        manifest_path = (
            Path(__file__).resolve().parent.parent
            / "benchmarks"
            / "gauntlet"
            / "scenarios"
            / "adversarial"
            / "manifest.json"
        )
        if not manifest_path.exists():
            pytest.skip("adversarial manifest not present")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_manifest_has_fixtures(self, manifest):
        assert "fixtures" in manifest
        assert len(manifest["fixtures"]) >= 5

    def test_fixture_fields(self, manifest):
        required = {"id", "title", "directory", "expected_signal", "harmful_action", "rationale"}
        for fixture in manifest["fixtures"]:
            assert required.issubset(set(fixture.keys())), f"Missing fields in {fixture.get('id')}"

    def test_fixture_directories_exist(self, manifest):
        base = (
            Path(__file__).resolve().parent.parent
            / "benchmarks"
            / "gauntlet"
            / "scenarios"
            / "adversarial"
        )
        for fixture in manifest["fixtures"]:
            d = base / fixture["directory"]
            assert d.exists(), f"Directory missing: {d}"
            py_files = list(d.glob("*.py"))
            assert len(py_files) > 0, f"No Python files in {d}"
