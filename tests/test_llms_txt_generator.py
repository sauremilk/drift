"""Regression tests for ``scripts/generate_llms_txt.py`` (Paket 1C, ADR-092).

llms.txt is the public LLM-discovery surface. These tests guard the
determinism, drift-detection, and coverage contracts that make the
file safe to autogenerate:

1. ``--check`` mode exits 0 on a clean tree and 1 on any drift.
2. Regeneration is idempotent (content-stable across repeat runs).
3. Every core signal registered in ``signal_registry`` appears in the
   rendered signal table.
4. The version line on disk matches ``pyproject.toml``.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LLMS_TXT = REPO_ROOT / "llms.txt"
GENERATOR = REPO_ROOT / "scripts" / "generate_llms_txt.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- trusted fixed script path
        [sys.executable, str(GENERATOR), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _project_version() -> str:
    with PYPROJECT.open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


class TestGeneratorContract:
    def test_check_mode_passes_on_clean_tree(self) -> None:
        """llms.txt on disk must stay in sync with the generator."""
        result = _run_generator("--check")
        assert result.returncode == 0, (
            f"generate_llms_txt.py --check failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
            "Fix: `python scripts/generate_llms_txt.py --write`"
        )

    def test_regeneration_is_idempotent(self, tmp_path: Path) -> None:
        """Two consecutive writes to a scratch path produce byte-identical output."""
        target = tmp_path / "llms.txt"
        first = _run_generator("--write", "--output", str(target))
        assert first.returncode == 0
        content_1 = target.read_bytes()

        second = _run_generator("--write", "--output", str(target))
        assert second.returncode == 0
        content_2 = target.read_bytes()

        assert content_1 == content_2, "Generator output is not deterministic"

    def test_check_mode_detects_drift(self, tmp_path: Path) -> None:
        """--check must exit 1 when the file on disk diverges."""
        target = tmp_path / "llms.txt"
        _run_generator("--write", "--output", str(target))
        # Corrupt the version line
        original = target.read_text(encoding="utf-8")
        corrupted = original.replace("Release status:", "Release status: v0.0.0 (was ")
        target.write_text(corrupted, encoding="utf-8")

        result = _run_generator("--check", "--output", str(target))
        assert result.returncode == 1
        assert "out of date" in result.stderr


class TestContentContract:
    @pytest.fixture(scope="class")
    def llms_text(self) -> str:
        return LLMS_TXT.read_text(encoding="utf-8")

    def test_version_matches_pyproject(self, llms_text: str) -> None:
        expected = _project_version()
        match = re.search(r"Release status:\s*v([\d]+\.[\d]+\.[\d]+)", llms_text)
        assert match, "Release status line missing from llms.txt"
        assert match.group(1) == expected, (
            f"llms.txt Release status ({match.group(1)}) != "
            f"pyproject.toml version ({expected})"
        )

    def test_all_core_signal_abbrevs_listed(self, llms_text: str) -> None:
        """Every core signal registered in signal_registry must appear."""
        from drift.signal_registry import get_all_meta

        core_abbrevs = {m.abbrev for m in get_all_meta() if m.is_core}
        # Parse rendered abbreviations from the signals section.
        rendered = set(re.findall(r"^- ([A-Z]{3}):\s", llms_text, flags=re.MULTILINE))
        missing = core_abbrevs - rendered
        assert not missing, f"Signals missing from llms.txt: {sorted(missing)}"

    def test_scoring_active_and_report_only_counts_consistent(
        self, llms_text: str
    ) -> None:
        """The section headers must agree with the number of rendered rows."""
        from drift.signal_registry import get_all_meta

        active = [m for m in get_all_meta() if m.is_core and m.default_weight > 0.0]
        report = [m for m in get_all_meta() if m.is_core and m.default_weight == 0.0]

        active_header = re.search(
            r"Scoring-active \((\d+),", llms_text,
        )
        report_header = re.search(
            r"Report-only \((\d+),", llms_text,
        )
        assert active_header, "Scoring-active header missing"
        assert report_header, "Report-only header missing"
        assert int(active_header.group(1)) == len(active)
        assert int(report_header.group(1)) == len(report)

    def test_weights_match_registry_defaults(self, llms_text: str) -> None:
        """Every weight printed in llms.txt must equal the registry default."""
        from drift.signal_registry import get_all_meta

        by_abbrev = {m.abbrev: m.default_weight for m in get_all_meta() if m.is_core}
        # Pattern: "- ABC: ...(weight 0.16...)" — weight always present.
        for abbrev, weight_str in re.findall(
            r"^- ([A-Z]{3}):[^\n]*\(weight\s+([\d.]+)", llms_text, flags=re.MULTILINE
        ):
            expected = by_abbrev.get(abbrev)
            if expected is None:
                continue  # Plugin or unknown signal — not our contract here
            assert abs(float(weight_str) - expected) < 1e-9, (
                f"Weight mismatch for {abbrev}: llms.txt={weight_str}, "
                f"registry={expected}"
            )
