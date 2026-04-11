"""Golden-file snapshot tests for the benchmark corpus.

Runs ``drift analyze`` on ``benchmarks/corpus/`` and compares the
output (JSON + SARIF) against a committed snapshot.  Any *unexpected*
change in findings, counts, scores, or structure causes a failure —
catching behavioral regressions that schema-only contract tests miss.

Usage:
    # Normal CI run (asserts match)
    pytest tests/test_golden_snapshot.py -v

    # Regenerate golden files after deliberate changes
    pytest tests/test_golden_snapshot.py --update-golden -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from drift.analyzer import analyze_repo
from drift.config import DriftConfig
from drift.output.json_output import analysis_to_json, findings_to_sarif

CORPUS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "corpus"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# Fields that change between runs and must be stripped before comparison.
_VOLATILE_KEYS = frozenset({
    "analyzed_at",
    "version",
    "analysis_duration_seconds",
    "repo",  # absolute workspace path differs between local and CI runners
    "trend",  # accumulates history across runs — non-deterministic
})

_VOLATILE_SARIF_KEYS = frozenset({
    "version",  # tool driver version
    "trend",  # drift trend history is non-deterministic across runs
})


# ── Helpers ───────────────────────────────────────────────────────────────


def _strip_volatile(obj: object) -> object:
    """Recursively remove volatile keys from a JSON-like structure."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile(item) for item in obj]
    return obj


def _strip_volatile_sarif(obj: object) -> object:
    """Remove volatile keys from SARIF output."""
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for k, v in obj.items():
            if k in _VOLATILE_SARIF_KEYS:
                continue
            # Strip tool driver version
            if k == "driver" and isinstance(v, dict):
                v = {dk: dv for dk, dv in v.items() if dk != "semanticVersion"}
            out[k] = _strip_volatile_sarif(v)
        return out
    if isinstance(obj, list):
        return [_strip_volatile_sarif(item) for item in obj]
    return obj


def _run_corpus_analysis() -> tuple[str, str]:
    """Analyze the benchmark corpus and return (json_str, sarif_str)."""
    cache_dir = Path(tempfile.mkdtemp(prefix=".drift-cache-golden-", dir=CORPUS_DIR))

    try:
        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
            cache_dir=str(cache_dir),
            embeddings_enabled=False,
        )
        analysis = analyze_repo(CORPUS_DIR, config=config, since_days=0)
        json_str = analysis_to_json(analysis)
        sarif_str = findings_to_sarif(analysis)
        return json_str, sarif_str
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def _canonical_json(raw: str, strip_fn: object = _strip_volatile) -> str:
    """Parse, strip volatile fields, re-serialize with sorted keys."""
    data = json.loads(raw)
    cleaned = strip_fn(data)  # type: ignore[operator]
    return json.dumps(cleaned, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def corpus_output() -> tuple[str, str]:
    """Cache a single corpus analysis for the entire module."""
    return _run_corpus_analysis()


class TestJsonGoldenSnapshot:
    """Compare JSON output against golden file."""

    GOLDEN = GOLDEN_DIR / "corpus_snapshot.json"

    def test_json_snapshot(
        self,
        corpus_output: tuple[str, str],
        request: pytest.FixtureRequest,
    ) -> None:
        json_raw, _ = corpus_output
        canonical = _canonical_json(json_raw, _strip_volatile)

        if request.config.getoption("--update-golden"):
            self.GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            self.GOLDEN.write_text(canonical, encoding="utf-8")
            pytest.skip("Golden file updated — re-run without --update-golden")

        if not self.GOLDEN.exists():
            pytest.fail(
                f"Golden file missing: {self.GOLDEN}\n"
                "Run: pytest tests/test_golden_snapshot.py --update-golden"
            )

        expected = _canonical_json(
            self.GOLDEN.read_text(encoding="utf-8"),
            _strip_volatile,
        )
        if canonical != expected:
            # Provide actionable diff summary
            actual_data = json.loads(canonical)
            expected_data = json.loads(expected)
            diff_keys = _dict_diff_summary(expected_data, actual_data)
            pytest.fail(
                f"JSON golden snapshot mismatch.\n"
                f"Differences: {diff_keys}\n"
                f"Run: pytest tests/test_golden_snapshot.py --update-golden\n"
                f"to accept the new baseline."
            )


class TestSarifGoldenSnapshot:
    """Compare SARIF output against golden file."""

    GOLDEN = GOLDEN_DIR / "corpus_snapshot.sarif"

    def test_sarif_snapshot(
        self,
        corpus_output: tuple[str, str],
        request: pytest.FixtureRequest,
    ) -> None:
        _, sarif_raw = corpus_output
        canonical = _canonical_json(sarif_raw, _strip_volatile_sarif)

        if request.config.getoption("--update-golden"):
            self.GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            self.GOLDEN.write_text(canonical, encoding="utf-8")
            pytest.skip("Golden file updated — re-run without --update-golden")

        if not self.GOLDEN.exists():
            pytest.fail(
                f"Golden file missing: {self.GOLDEN}\n"
                "Run: pytest tests/test_golden_snapshot.py --update-golden"
            )

        expected = _canonical_json(
            self.GOLDEN.read_text(encoding="utf-8"),
            _strip_volatile_sarif,
        )
        if canonical != expected:
            actual_data = json.loads(canonical)
            expected_data = json.loads(expected)
            diff_keys = _dict_diff_summary(expected_data, actual_data)
            pytest.fail(
                f"SARIF golden snapshot mismatch.\n"
                f"Differences: {diff_keys}\n"
                f"Run: pytest tests/test_golden_snapshot.py --update-golden\n"
                f"to accept the new baseline."
            )


def _dict_diff_summary(
    expected: object, actual: object, path: str = "$"
) -> list[str]:
    """Return a list of human-readable diff descriptions (max 15)."""
    diffs: list[str] = []

    def _walk(exp: object, act: object, p: str) -> None:
        if len(diffs) >= 15:
            return
        if type(exp) is not type(act):
            diffs.append(f"{p}: type {type(exp).__name__} → {type(act).__name__}")
            return
        if isinstance(exp, dict) and isinstance(act, dict):
            all_keys = set(exp) | set(act)
            for k in sorted(all_keys):
                if k not in act:
                    diffs.append(f"{p}.{k}: removed")
                elif k not in exp:
                    diffs.append(f"{p}.{k}: added")
                else:
                    _walk(exp[k], act[k], f"{p}.{k}")
        elif isinstance(exp, list) and isinstance(act, list):
            if len(exp) != len(act):
                diffs.append(f"{p}: list length {len(exp)} → {len(act)}")
            for i, (e, a) in enumerate(zip(exp, act, strict=False)):
                _walk(e, a, f"{p}[{i}]")
        elif exp != act:
            diffs.append(f"{p}: {_short(exp)} → {_short(act)}")

    def _short(v: object) -> str:
        s = repr(v)
        return s[:60] + "…" if len(s) > 60 else s

    _walk(expected, actual, path)
    return diffs
