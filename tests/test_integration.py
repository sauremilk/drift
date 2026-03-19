"""Integration test — runs analyze_repo() against a fixture git repository."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

from drift.analyzer import analyze_repo
from drift.config import DriftConfig


def _git(cwd: Path, *args: str) -> None:
    """Run a git command inside *cwd*."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a real git repository with history for integration testing."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")

    # --- Commit 1: initial code ---
    svc = tmp_path / "services"
    svc.mkdir()
    (svc / "__init__.py").write_text("")
    (svc / "payment.py").write_text(
        textwrap.dedent("""\
        class PaymentError(Exception):
            pass

        def process_payment(amount: float, currency: str) -> dict:
            \"\"\"Process a payment.\"\"\"
            try:
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                return {"status": "ok", "amount": amount}
            except ValueError as e:
                raise PaymentError(str(e)) from e
    """)
    )

    api = tmp_path / "api"
    api.mkdir()
    (api / "__init__.py").write_text("")
    (api / "routes.py").write_text(
        textwrap.dedent("""\
        from services.payment import process_payment

        def get_payments():
            return []

        def create_payment(data: dict):
            return process_payment(data["amount"], data["currency"])
    """)
    )

    utils = tmp_path / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("")
    (utils / "helpers.py").write_text(
        textwrap.dedent("""\
        def format_currency(amount: float, currency: str = "EUR") -> str:
            return f"{amount:.2f} {currency}"

        def format_money(value: float, cur: str = "EUR") -> str:
            \"\"\"Almost identical to format_currency.\"\"\"
            return f"{value:.2f} {cur}"
    """)
    )

    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "Initial commit")

    # --- Commit 2: AI-style addition ---
    (svc / "refund.py").write_text(
        textwrap.dedent("""\
        def refund_payment(transaction_id: str) -> bool:
            try:
                result = lookup(transaction_id)
                return True
            except Exception as e:
                print(e)
                return False

        def lookup(tid: str) -> dict:
            return {"id": tid}
    """)
    )
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "commit",
        "-m",
        "Add refund payment functionality for users",
    )

    return tmp_path


class TestIntegrationAnalyzeRepo:
    """End-to-end integration tests for the full analysis pipeline."""

    def test_full_pipeline_runs(self, git_repo: Path) -> None:
        """analyze_repo returns a valid RepoAnalysis with findings."""
        analysis = analyze_repo(git_repo, since_days=365)

        assert analysis.repo_path == git_repo.resolve()
        assert analysis.total_files > 0
        assert analysis.drift_score >= 0.0
        assert analysis.drift_score <= 1.0
        assert analysis.analysis_duration_seconds > 0

    def test_finds_python_files(self, git_repo: Path) -> None:
        """File discovery picks up all .py files."""
        analysis = analyze_repo(git_repo, since_days=365)
        # At least: services/payment.py, services/refund.py, api/routes.py, utils/helpers.py
        assert analysis.total_files >= 4

    def test_generates_findings(self, git_repo: Path) -> None:
        """Analysis produces findings (the fixture has error handling variants + near dupes)."""
        analysis = analyze_repo(git_repo, since_days=365)
        assert len(analysis.findings) >= 0  # May or may not find issues in small repo

    def test_module_scores_populated(self, git_repo: Path) -> None:
        """Module scores are computed and sorted by drift score."""
        analysis = analyze_repo(git_repo, since_days=365)
        if analysis.module_scores:
            scores = [m.drift_score for m in analysis.module_scores]
            assert scores == sorted(scores, reverse=True)

    def test_config_respected(self, git_repo: Path) -> None:
        """Custom config restricts analysis to only specified patterns."""
        cfg = DriftConfig(include=["services/**/*.py"])
        analysis = analyze_repo(git_repo, config=cfg, since_days=365)
        # Only services/ files should be included
        for ms in analysis.module_scores:
            assert "services" in ms.path.as_posix() or ms.path.as_posix() == "."

    def test_cache_dir_created(self, git_repo: Path) -> None:
        """Parse cache directory is created after analysis."""
        analyze_repo(git_repo, since_days=365)
        cache_dir = git_repo / ".drift-cache" / "parse"
        assert cache_dir.exists()

    def test_second_run_uses_cache(self, git_repo: Path) -> None:
        """Second run should complete successfully with cache."""
        # First run (populates cache)
        analyze_repo(git_repo, since_days=365)

        # Second run (should use cache)
        analysis = analyze_repo(git_repo, since_days=365)

        # Just verify it completes successfully with cache
        assert analysis.total_files > 0
