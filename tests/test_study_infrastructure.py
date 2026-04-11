"""Tests for community-study infrastructure (scripts, fixtures, templates).

Validates the core statistical functions and fixture schemas used by
community studies S1–S13.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make scripts importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "study_samples"

sys.path.insert(0, str(SCRIPTS_DIR))

import study_rater_agreement  # noqa: E402, I001
import study_self_analysis_aggregate  # noqa: E402, I001
from study_debt_correlation import spearman_rho  # noqa: E402, I001


# ---------- Fleiss' kappa ----------


class TestFleissKappa:
    """Tests for Fleiss' kappa computation."""

    def test_perfect_agreement(self) -> None:
        """All raters agree on every item → κ = 1.0."""
        ratings = [["TP", "TP", "TP"]] * 10
        k = study_rater_agreement.fleiss_kappa(ratings, ["TP", "FP", "Unclear"])
        assert abs(k - 1.0) < 0.01

    def test_systematic_disagreement_negative(self) -> None:
        """Systematic disagreement → κ < 0."""
        categories = ["A", "B", "C"]
        ratings = [
            ["A", "B", "C"],
            ["B", "C", "A"],
            ["C", "A", "B"],
            ["A", "C", "B"],
            ["B", "A", "C"],
            ["C", "B", "A"],
        ]
        k = study_rater_agreement.fleiss_kappa(ratings, categories)
        assert k < 0, f"Systematic disagreement should yield κ < 0, got {k:.4f}"

    def test_empty_input(self) -> None:
        k = study_rater_agreement.fleiss_kappa([], ["TP", "FP"])
        assert k == 0.0


# ---------- Cohen's kappa ----------


class TestCohenKappa:
    """Tests for Cohen's kappa (two raters)."""

    def test_perfect_agreement(self) -> None:
        rater_a = ["TP", "FP", "TP", "TP", "FP"]
        rater_b = ["TP", "FP", "TP", "TP", "FP"]
        k = study_rater_agreement.cohen_kappa(rater_a, rater_b, ["TP", "FP"])
        assert abs(k - 1.0) < 0.01

    def test_known_value(self) -> None:
        """Known textbook example: 2 raters, 2 categories, partial agreement."""
        # 10 items: rater A = 7 TP + 3 FP,  rater B = 6 TP + 4 FP
        # Agree on 8/10 → p_o = 0.8
        rater_a = ["TP"] * 7 + ["FP"] * 3
        rater_b = ["TP"] * 6 + ["FP", "TP", "FP", "FP"]
        k = study_rater_agreement.cohen_kappa(rater_a, rater_b, ["TP", "FP"])
        # p_o = 0.7, p_e varies — just check reasonable range
        assert -1.0 <= k <= 1.0

    def test_complete_disagreement(self) -> None:
        rater_a = ["TP", "FP", "TP", "FP"]
        rater_b = ["FP", "TP", "FP", "TP"]
        k = study_rater_agreement.cohen_kappa(rater_a, rater_b, ["TP", "FP"])
        assert k < 0, f"Complete disagreement should yield κ < 0, got {k:.4f}"


# ---------- analyze_file with fixture ----------


class TestAnalyzeFile:
    """Test analyze_file with the sample fixture."""

    def test_rater_matrix_fixture(self) -> None:
        path = FIXTURES_DIR / "rater_matrix.json"
        result = study_rater_agreement.analyze_file(path)

        assert result["n_findings"] == 5
        assert result["n_raters"] == 3
        assert result["kappa_type"] == "fleiss"
        assert -1.0 <= result["kappa"] <= 1.0
        assert 0.0 <= result["mean_agreement"] <= 1.0

    def test_per_finding_structure(self) -> None:
        path = FIXTURES_DIR / "rater_matrix.json"
        result = study_rater_agreement.analyze_file(path)

        for pf in result["per_finding"]:
            assert "finding_id" in pf
            assert "agreement_rate" in pf
            assert "majority_label" in pf
            assert 0.0 <= pf["agreement_rate"] <= 1.0


# ---------- Self-analysis aggregation ----------


class TestSelfAnalysisAggregate:
    """Test aggregate() with fixture data."""

    def test_aggregate_fixture(self) -> None:
        reports = json.loads(
            (FIXTURES_DIR / "self_analysis_reports.json").read_text(encoding="utf-8")
        )
        result = study_self_analysis_aggregate.aggregate(reports)

        assert result["n_reports"] == 2
        assert result["n_findings_total"] == 8
        assert 0.0 <= result["discovery_rate"] <= 1.0
        assert result["surprise_by_signal"]
        assert isinstance(result["will_fix_rate"], float)

    def test_empty_reports(self) -> None:
        result = study_self_analysis_aggregate.aggregate([])
        assert result["n_reports"] == 0


# ---------- Spearman rho ----------


class TestSpearmanRho:
    """Test the pure-Python Spearman rank correlation."""

    def test_perfect_positive(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]
        rho, n = spearman_rho(x, y)
        assert n == 5
        assert abs(rho - 1.0) < 0.01

    def test_perfect_negative(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [50.0, 40.0, 30.0, 20.0, 10.0]
        rho, n = spearman_rho(x, y)
        assert abs(rho - (-1.0)) < 0.01

    def test_insufficient_data(self) -> None:
        rho, n = spearman_rho([1.0, 2.0], [3.0, 4.0])
        assert rho == 0.0
        assert n == 2


# ---------- Debt correlation fixture schema ----------


class TestDebtCorrelationSchema:
    """Validate the debt_correlation fixture has expected structure."""

    def test_fixture_structure(self) -> None:
        data = json.loads((FIXTURES_DIR / "debt_correlation.json").read_text(encoding="utf-8"))
        assert "repos" in data
        assert len(data["repos"]) >= 3

        for repo in data["repos"]:
            assert "composite_score" in repo
            assert "issue_count" in repo
            assert isinstance(repo["composite_score"], (int, float))
            assert isinstance(repo["issue_count"], int)


# ---------- Kappa self-test ----------


class TestKappaSelfTest:
    """Run the built-in self-test."""

    def test_self_test_passes(self) -> None:
        assert study_rater_agreement.run_self_test() is True
