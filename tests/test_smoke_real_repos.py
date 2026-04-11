"""Smoke tests on real repositories.

Validates that drift produces sensible results on actual codebases,
catching false-positive regressions and signal failures that curated
fixtures cannot surface.

Usage:
    pytest tests/test_smoke_real_repos.py -v              # self-analysis only
    pytest tests/test_smoke_real_repos.py -v -m slow      # clone tests only
    pytest tests/test_smoke_real_repos.py -v --run-slow   # all including clones
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from drift.analyzer import analyze_repo
from drift.config import DriftConfig
from drift.models import RepoAnalysis, Severity, SignalType
from drift.output.json_output import analysis_to_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DRIFT_REPO = Path(__file__).resolve().parent.parent  # drift/ repo root
BENCHMARK_DIR = DRIFT_REPO / "benchmark_results"
DEFAULT_SMOKE_CACHE_DIR = DRIFT_REPO / ".tmp_smoke_repo_cache"
PR_SMOKE_REPOS = {"requests", "fastapi", "pydantic"}


def _save_findings_json(
    analysis: RepoAnalysis, repo_name: str, request: pytest.FixtureRequest
) -> None:
    """Persist full analysis JSON when --save-findings is active."""
    if not request.config.getoption("--save-findings", default=False):
        return
    BENCHMARK_DIR.mkdir(exist_ok=True)
    dest = BENCHMARK_DIR / f"{repo_name}_full.json"
    dest.write_text(analysis_to_json(analysis), encoding="utf-8")
    print(f"\n  [save-findings] Wrote {dest}")


def _shallow_clone(url: str, dest: Path, depth: int = 1, timeout: int = 120) -> Path:
    """Shallow-clone a git repo. Returns the clone directory."""
    subprocess.run(
        ["git", "clone", "--depth", str(depth), "--single-branch", url, str(dest)],
        check=True,
        capture_output=True,
        timeout=timeout,
    )
    return dest


def _prepare_cached_clone(
    name: str,
    url: str,
    cache_root: Path,
    *,
    timeout: int = 120,
    refresh: bool = False,
) -> Path:
    """Reuse cached clones between runs; refresh only when requested."""
    cache_root.mkdir(parents=True, exist_ok=True)
    clone_dir = cache_root / name

    if refresh and clone_dir.exists():
        shutil.rmtree(clone_dir, ignore_errors=True)

    if (clone_dir / ".git").exists():
        return clone_dir

    return _shallow_clone(url, clone_dir, timeout=timeout)


def _assert_analysis_sane(analysis: RepoAnalysis, label: str) -> None:
    """Common assertions that any valid analysis must satisfy."""
    assert analysis.total_files > 0, f"{label}: no files discovered"
    assert 0.0 <= analysis.drift_score <= 1.0, f"{label}: score out of range"
    assert analysis.analysis_duration_seconds > 0, f"{label}: zero duration"
    # Every finding must have a signal type and valid score
    for f in analysis.findings:
        assert f.signal_type is not None, f"{label}: finding without signal type"
        assert 0.0 <= f.score <= 1.0, f"{label}: finding score out of range: {f.score}"


def _signal_distribution(analysis: RepoAnalysis) -> dict[SignalType, int]:
    """Count findings per signal type."""
    dist: dict[SignalType, int] = {}
    for f in analysis.findings:
        dist[f.signal_type] = dist.get(f.signal_type, 0) + 1
    return dist


def _severity_distribution(analysis: RepoAnalysis) -> dict[Severity, int]:
    """Count findings per severity level."""
    dist: dict[Severity, int] = {}
    for f in analysis.findings:
        dist[f.severity] = dist.get(f.severity, 0) + 1
    return dist


# ---------------------------------------------------------------------------
# Self-analysis: drift repo (always available, no network)
# ---------------------------------------------------------------------------


class TestSelfAnalysis:
    """Run drift on its own codebase — the cheapest real-world smoke test."""

    @pytest.fixture(scope="class")
    def analysis(self) -> RepoAnalysis:
        """Analyze the drift repo itself. Cached per class."""
        config = DriftConfig(
            include=["**/*.py"],
            exclude=[
                "**/__pycache__/**",
                "**/node_modules/**",
                "**/.venv*/**",
                "**/.tmp_*venv*/**",
                "**/.python-toolcache/**",
            ],
            embeddings_enabled=False,
        )
        return analyze_repo(DRIFT_REPO, config=config, since_days=365)

    def test_analysis_completes(self, analysis: RepoAnalysis) -> None:
        """Full pipeline runs without errors on drift itself."""
        _assert_analysis_sane(analysis, "drift-self")

    def test_file_count_reasonable(self, analysis: RepoAnalysis) -> None:
        """Drift repo should have a known range of Python files."""
        # Guardrail: file discovery should stay non-trivial but below implausible runaway values.
        # The repository now contains generated docs/artifacts and larger benchmark fixtures.
        assert 20 <= analysis.total_files <= 10_000, (
            f"Unexpected file count: {analysis.total_files}"
        )

    def test_drift_score_in_range(self, analysis: RepoAnalysis) -> None:
        """Self-analysis score should be in the expected range.

        STUDY.md baseline: 0.442. Allow +/-0.25 for codebase evolution.
        """
        assert 0.15 <= analysis.drift_score <= 0.70, (
            f"Self-analysis score {analysis.drift_score:.3f} outside expected range"
        )

    def test_no_critical_findings(self, analysis: RepoAnalysis) -> None:
        """A well-maintained tool repo should have no CRITICAL findings."""
        criticals = analysis.findings_by_severity(Severity.CRITICAL)
        assert len(criticals) == 0, f"Unexpected CRITICAL findings: {[f.title for f in criticals]}"

    def test_multiple_signals_fire(self, analysis: RepoAnalysis) -> None:
        """At least 2 distinct signal types should produce findings."""
        dist = _signal_distribution(analysis)
        assert len(dist) >= 2, f"Only {len(dist)} signal type(s) fired: {list(dist.keys())}"

    def test_findings_have_file_paths(self, analysis: RepoAnalysis) -> None:
        """Every finding should reference a concrete file."""
        for f in analysis.findings:
            assert f.file_path is not None, f"Finding without file_path: {f.title}"

    def test_signal_distribution_report(
        self, analysis: RepoAnalysis, request: pytest.FixtureRequest
    ) -> None:
        """Print signal distribution for manual inspection (always passes)."""
        _save_findings_json(analysis, "drift_self", request)
        dist = _signal_distribution(analysis)
        sev = _severity_distribution(analysis)
        print(f"\n{'=' * 60}")
        print("Drift Self-Analysis Smoke Report")
        print(f"{'=' * 60}")
        print(f"  Score:     {analysis.drift_score:.3f}")
        print(f"  Files:     {analysis.total_files}")
        print(f"  Functions: {analysis.total_functions}")
        print(f"  Findings:  {len(analysis.findings)}")
        print("\n  Signal distribution:")
        for sig, count in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"    {sig.value:<30s} {count:>4d}")
        print("\n  Severity distribution:")
        for sv, count in sorted(sev.items(), key=lambda x: -x[1]):
            print(f"    {sv.value:<12s} {count:>4d}")


# ---------------------------------------------------------------------------
# External repos: cloned on demand (marked slow)
# ---------------------------------------------------------------------------

# Each entry: (name, git_url, expected_score_min, expected_score_max,
#              min_files, expected_signals_present, clone_timeout)
# clone_timeout defaults to 120s; large repos like django need more.
EXTERNAL_REPOS = [
    # --- Baseline: small, hand-crafted libraries ---
    (
        "httpx",
        "https://github.com/encode/httpx.git",
        0.10,
        0.65,
        15,  # core package ~23 .py files (tests/docs excluded)
        {SignalType.EXPLAINABILITY_DEFICIT},
        120,
    ),
    (
        "flask",
        "https://github.com/pallets/flask.git",
        0.05,  # small, clean, well-maintained → expect low drift
        0.55,
        10,  # core flask/ package
        {SignalType.EXPLAINABILITY_DEFICIT},
        120,
    ),
    (
        "requests",
        "https://github.com/psf/requests.git",
        0.05,  # similar to httpx, small focused library
        0.60,
        8,  # core requests/ package
        {SignalType.EXPLAINABILITY_DEFICIT},
        120,
    ),
    # --- Stress: large frameworks with known complexity ---
    (
        "fastapi",
        "https://github.com/fastapi/fastapi.git",
        0.15,  # expect moderate drift (docs_src now excluded by default)
        0.75,
        30,  # core fastapi/ package without docs_src
        {SignalType.PATTERN_FRAGMENTATION},
        120,
    ),
    (
        "django",
        "https://github.com/django/django.git",
        0.20,  # mega-repo, historically grown → expect higher drift
        0.85,
        500,  # huge codebase
        {SignalType.PATTERN_FRAGMENTATION, SignalType.MUTANT_DUPLICATE},
        300,  # large repo needs more clone time
    ),
    # --- Structural diversity: dataclass-heavy, cross-author comparison ---
    (
        "pydantic",
        "https://github.com/pydantic/pydantic.git",
        0.15,  # complex metaclass internals, many model patterns
        0.75,
        30,  # core pydantic/ package
        {SignalType.EXPLAINABILITY_DEFICIT},
        120,
    ),
    (
        "sqlmodel",
        "https://github.com/fastapi/sqlmodel.git",
        0.10,  # small, from fastapi author → cross-repo comparison
        0.65,
        5,  # small core
        set(),  # no specific signal expectation — exploratory
        120,
    ),
]


@pytest.mark.slow
class TestExternalRepos:
    """Clone and analyze real open-source repos. Requires network."""

    @pytest.fixture(scope="session")
    def external_repo_root(self, request: pytest.FixtureRequest) -> Path:
        """Return the cache directory for cloned external repositories."""
        configured = os.getenv("DRIFT_SMOKE_CACHE_DIR", "").strip()
        return Path(configured) if configured else DEFAULT_SMOKE_CACHE_DIR

    @pytest.fixture(scope="session")
    def smoke_profile(self, request: pytest.FixtureRequest) -> str:
        """Read the selected external smoke profile."""
        return request.config.getoption("--smoke-profile", default="pr")

    @pytest.fixture(scope="session")
    def refresh_smoke_cache(self, request: pytest.FixtureRequest) -> bool:
        """Whether cached clones should be refreshed before analysis."""
        return bool(request.config.getoption("--refresh-smoke-cache", default=False))

    @pytest.fixture(scope="session", params=EXTERNAL_REPOS, ids=[r[0] for r in EXTERNAL_REPOS])
    def repo_analysis(
        self,
        request: pytest.FixtureRequest,
        external_repo_root: Path,
        smoke_profile: str,
        refresh_smoke_cache: bool,
    ) -> tuple[str, RepoAnalysis]:
        name, url, score_min, score_max, min_files, expected_signals, clone_timeout = request.param

        if smoke_profile == "pr" and name not in PR_SMOKE_REPOS:
            pytest.skip(f"{name} excluded by smoke profile 'pr'")

        try:
            clone_dir = _prepare_cached_clone(
                name,
                url,
                external_repo_root,
                timeout=clone_timeout,
                refresh=refresh_smoke_cache,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            pytest.skip(f"Could not clone {name}: {exc}")

        config = DriftConfig(
            include=["**/*.py"],
            exclude=[
                "**/__pycache__/**",
                "**/node_modules/**",
                "**/.venv*/**",
                "**/docs/**",
                "**/docs_src/**",
                "**/examples/**",
                "**/tests/**",
                "**/test_*",
            ],
            embeddings_enabled=False,
        )
        analysis = analyze_repo(clone_dir, config=config, since_days=365)
        return name, analysis

    def test_analysis_completes(self, repo_analysis: tuple[str, RepoAnalysis]) -> None:
        name, analysis = repo_analysis
        _assert_analysis_sane(analysis, name)

    def test_score_in_expected_range(
        self, repo_analysis: tuple[str, RepoAnalysis], request: pytest.FixtureRequest
    ) -> None:
        name, analysis = repo_analysis
        params = next(r for r in EXTERNAL_REPOS if r[0] == name)
        _, _, score_min, score_max, *_ = params
        assert score_min <= analysis.drift_score <= score_max, (
            f"{name}: score {analysis.drift_score:.3f} outside [{score_min}, {score_max}]"
        )

    def test_minimum_files_discovered(
        self, repo_analysis: tuple[str, RepoAnalysis], request: pytest.FixtureRequest
    ) -> None:
        name, analysis = repo_analysis
        params = next(r for r in EXTERNAL_REPOS if r[0] == name)
        min_files = params[4]
        assert analysis.total_files >= min_files, (
            f"{name}: only {analysis.total_files} files, expected >= {min_files}"
        )

    def test_expected_signals_fire(
        self, repo_analysis: tuple[str, RepoAnalysis], request: pytest.FixtureRequest
    ) -> None:
        name, analysis = repo_analysis
        params = next(r for r in EXTERNAL_REPOS if r[0] == name)
        expected_signals = params[5]
        actual_signals = {f.signal_type for f in analysis.findings}
        missing = expected_signals - actual_signals
        assert not missing, f"{name}: expected signals not found: {[s.value for s in missing]}"

    def test_no_critical_on_maintained_repo(self, repo_analysis: tuple[str, RepoAnalysis]) -> None:
        name, analysis = repo_analysis
        criticals = analysis.findings_by_severity(Severity.CRITICAL)
        # Well-maintained repos should have very few criticals
        assert len(criticals) <= 5, (
            f"{name}: too many CRITICAL findings ({len(criticals)}): "
            f"{[f.title for f in criticals[:5]]}"
        )

    def test_smoke_report(
        self,
        repo_analysis: tuple[str, RepoAnalysis],
        request: pytest.FixtureRequest,
    ) -> None:
        """Print findings summary for manual FP review (always passes)."""
        name, analysis = repo_analysis
        _save_findings_json(analysis, name, request)
        dist = _signal_distribution(analysis)
        sev = _severity_distribution(analysis)
        print(f"\n{'=' * 60}")
        print(f"Smoke Report: {name}")
        print(f"{'=' * 60}")
        print(f"  Score:     {analysis.drift_score:.3f}")
        print(f"  Files:     {analysis.total_files}")
        print(f"  Functions: {analysis.total_functions}")
        print(f"  Findings:  {len(analysis.findings)}")
        print("\n  Signal distribution:")
        for sig, count in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"    {sig.value:<30s} {count:>4d}")
        print("\n  Severity distribution:")
        for sv, count in sorted(sev.items(), key=lambda x: -x[1]):
            print(f"    {sv.value:<12s} {count:>4d}")

        # Print top-5 HIGH findings for FP review
        highs = [f for f in analysis.findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
        if highs:
            print("\n  Top HIGH/CRITICAL findings (manual FP review):")
            for f in sorted(highs, key=lambda x: -x.score)[:5]:
                print(f"    [{f.signal_type}] {f.title}")
                print(f"      {f.file_path}:{f.start_line} score={f.score:.2f}")
