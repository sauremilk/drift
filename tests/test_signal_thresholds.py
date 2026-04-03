"""Threshold sensitivity tests for signal detectors.

Kill surviving mutants from signal_mutation_test.py by asserting
specific severity assignments, score ranges, and detection boundaries.

Each test targets one or more mutation IDs (documented in comments).
"""

from __future__ import annotations

import datetime
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import numpy as np

from drift.config import DriftConfig, LayerBoundary, PolicyConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import (
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.architecture_violation import (
    _compute_hub_nodes,
    _infer_layer_with_embeddings,
)
from drift.signals.base import AnalysisContext, create_signals

# ── Helper ────────────────────────────────────────────────────────────


def _run_signal(
    tmp_path: Path,
    files: dict[str, str],
    signal_type: SignalType,
    *,
    embeddings: bool = False,
    config: DriftConfig | None = None,
) -> list[Finding]:
    """Materialize files, parse, and run one signal detector."""
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir(exist_ok=True)

    for rel, content in files.items():
        p = fixture_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")

    if config is None:
        config = DriftConfig(
            include=["**/*.py"],
            exclude=[],
            embeddings_enabled=embeddings,
        )
    finfos = discover_files(fixture_dir, config.include, config.exclude)
    parse_results = [parse_file(fi.path, fixture_dir, fi.language) for fi in finfos]

    now = datetime.datetime.now(tz=datetime.UTC)
    file_histories: dict[str, FileHistory] = {}
    for fi in finfos:
        key = fi.path.as_posix()
        file_histories[key] = FileHistory(
            path=fi.path,
            total_commits=10,
            unique_authors=2,
            ai_attributed_commits=0,
            change_frequency_30d=0.5,
            defect_correlated_commits=0,
            last_modified=now - datetime.timedelta(days=30),
            first_seen=now - datetime.timedelta(days=120),
        )

    ctx = AnalysisContext(
        repo_path=fixture_dir,
        config=config,
        parse_results=parse_results,
        file_histories=file_histories,
        embedding_service=None,
    )

    for sig in create_signals(ctx):
        if sig.signal_type == signal_type:
            return sig.analyze(parse_results, file_histories, config)
    return []


# ── EDS: Explainability Deficit Signal ────────────────────────────────


class TestEDSThresholds:
    """Kill eds_002, eds_003, eds_006."""

    def _complex_func(self, complexity: int) -> str:
        """Generate a Python function with approximately `complexity` CC."""
        # Base CC = 1, each `if` adds +1
        branches = complexity - 1
        lines = ["def complex_func(a, b, c):"]
        for i in range(branches):
            indent = "    " * (i + 1)
            lines.append(f"{indent}if a > {i}:")
        lines.append("    " * (branches + 1) + "pass")
        # Add return and some LOC padding to meet min_func_loc
        lines.append("    result = a + b + c")
        lines.append("    x = result * 2")
        lines.append("    y = x + 1")
        lines.append("    z = y - 1")
        lines.append("    return z")
        return "\n".join(lines)

    def test_high_complexity_produces_finding(self, tmp_path: Path) -> None:
        """A function with complexity 12, no docstring, no test → EDS finding.

        Kills eds_006: mutation flips `< min_complexity` to `>= min_complexity`,
        which would suppress complex functions and pass simple ones.
        """
        files = {
            "__init__.py": "",
            "service.py": self._complex_func(12),
        }
        findings = _run_signal(tmp_path, files, SignalType.EXPLAINABILITY_DEFICIT)
        assert len(findings) >= 1, "Complex undocumented function should trigger EDS"

    def test_severity_medium_range(self, tmp_path: Path) -> None:
        """Function with moderate complexity → MEDIUM or LOW severity.

        Kills eds_002: mutation changes HIGH threshold 0.7 → 0.3,
        which would classify moderate-deficit functions as HIGH.
        """
        # Complexity 8, no docstring → deficit ≈ 1.0, complexity_factor = 8/20 = 0.4
        # weighted_score = 1.0 * 0.4 = 0.4 → should be LOW (0.3 ≤ 0.4 < 0.5)
        files = {
            "__init__.py": "",
            "service.py": self._complex_func(8),
        }
        findings = _run_signal(tmp_path, files, SignalType.EXPLAINABILITY_DEFICIT)
        assert len(findings) >= 1
        # With eds_002 mutation (0.7→0.3), this would be HIGH instead of LOW
        assert findings[0].severity in (Severity.LOW, Severity.MEDIUM)
        assert findings[0].severity != Severity.HIGH

    def test_score_moderate_with_normal_normalization(self, tmp_path: Path) -> None:
        """Complexity 14 → complexity_factor = 14/20 = 0.7. Score should be ≤0.7.

        Kills eds_003: mutation changes /20 → /2, inflating
        complexity_factor to min(1.0, 14/2) = 1.0, → score would be 1.0.
        """
        files = {
            "__init__.py": "",
            "service.py": self._complex_func(14),
        }
        findings = _run_signal(tmp_path, files, SignalType.EXPLAINABILITY_DEFICIT)
        assert len(findings) >= 1
        # Normal: score = deficit * (14/20) = 1.0 * 0.7 = 0.7
        # Mutated: score = deficit * min(1.0, 14/2) = 1.0 * 1.0 = 1.0
        assert findings[0].score <= 0.85, (
            f"Score {findings[0].score} too high — normalization suspect"
        )


# ── GCD: Guard Clause Deficit Signal ─────────────────────────────────


def _unguarded_func(name: str, params: list[str], complexity: int) -> str:
    """Generate a function with given params/complexity but no guard clauses."""
    sig = ", ".join(params)
    lines = [f"def {name}({sig}):"]
    # Add nested ifs for complexity
    for i in range(complexity - 1):
        indent = "    " * (i + 1)
        lines.append(f"{indent}if {params[0]} > {i}:")
    lines.append("    " * complexity + "pass")
    lines.append("    return None")
    return "\n".join(lines)


def _guarded_func(name: str, params: list[str]) -> str:
    """Generate a function WITH guard clauses."""
    sig = ", ".join(params)
    return textwrap.dedent(f"""\
        def {name}({sig}):
            if {params[0]} is None:
                raise ValueError("required")
            if {params[1]} is None:
                raise ValueError("required")
            result = {params[0]} + {params[1]}
            if result > 100:
                return result
            elif result > 50:
                return result // 2
            else:
                return 0
    """)


class TestGCDThresholds:
    """Kill gcd_001, gcd_003, gcd_004, gcd_005, gcd_006."""

    def test_single_param_excluded(self, tmp_path: Path) -> None:
        """Functions with <2 params should be excluded from GCD analysis.

        Kills gcd_001: mutation changes `< 2` to `< 0` (never skips).
        """
        files = {
            "__init__.py": "",
            "handlers/__init__.py": "",
            # 4 functions with only 1 param + high complexity
            "handlers/single.py": "\n\n".join(
                _unguarded_func(f"handle_{i}", ["data"], 6)
                for i in range(4)
            ),
        }
        findings = _run_signal(tmp_path, files, SignalType.GUARD_CLAUSE_DEFICIT)
        # With only 1-param functions, GCD should produce no module-level findings
        module_findings = [f for f in findings if "deficit" in f.title.lower()]
        assert len(module_findings) == 0, (
            "Single-param functions should be excluded from GCD analysis"
        )

    def test_guarded_module_excluded(self, tmp_path: Path) -> None:
        """Module with >15% guarded ratio should be skipped.

        Kills gcd_003: mutation changes `>= 0.15` to `>= 0.99`,
        so this well-guarded module would suddenly produce a finding.
        """
        files = {
            "__init__.py": "",
            "services/__init__.py": "",
        }
        # 4 functions: 1 guarded (25% ratio) + 3 unguarded
        files["services/guarded.py"] = _guarded_func("process", ["x", "y"])
        for i in range(3):
            files[f"services/worker_{i}.py"] = _unguarded_func(
                f"run_{i}", ["a", "b"], 6
            )
        findings = _run_signal(tmp_path, files, SignalType.GUARD_CLAUSE_DEFICIT)
        module_findings = [
            f for f in findings
            if "deficit" in f.title.lower() and "services" in str(f.file_path)
        ]
        # 1/4 guarded = 25% > 15% threshold → module should be SKIPPED
        assert len(module_findings) == 0, (
            f"Module with 25% guarded ratio should be skipped, got: {module_findings}"
        )

    def test_unguarded_module_severity(self, tmp_path: Path) -> None:
        """Module with low guarded ratio → MEDIUM severity (score < 0.7).

        Kills gcd_004: mutation changes score >= 0.7 to >= 0.1,
        making almost everything HIGH.

        Kills gcd_006: mutation changes /20 to /200, deflating scores
        drastically (e.g., 0.3 → 0.03).
        """
        # 3 unguarded functions with moderate complexity (6)
        # mean_complexity = 6, guarded_ratio = 0
        # score = min(1.0, (1-0) * 6 / 20) = 0.3 → MEDIUM (0.3 < 0.7)
        files = {
            "__init__.py": "",
            "api/__init__.py": "",
        }
        for i in range(3):
            files[f"api/handler_{i}.py"] = _unguarded_func(
                f"handle_{i}", ["request", "response"], 6
            )
        findings = _run_signal(tmp_path, files, SignalType.GUARD_CLAUSE_DEFICIT)
        module_findings = [
            f for f in findings
            if "deficit" in f.title.lower() and "api" in str(f.file_path)
        ]
        assert len(module_findings) >= 1, "Unguarded module should produce finding"
        sev = module_findings[0].severity
        score = module_findings[0].score
        assert sev == Severity.MEDIUM, f"Expected MEDIUM, got {sev}"
        # With /20: score = 0.3. With mutation /200: score = 0.03
        assert score >= 0.1, (
            f"Score {score} suspiciously low — normalization may be wrong"
        )

    def test_nesting_score_formula(self, tmp_path: Path) -> None:
        """Deep nesting should produce score starting at 0.3.

        Kills gcd_005: mutation changes base 0.3 to 0.9, inflating scores.
        """
        # Module needs ≥3 qualifying functions (gcd_min_public_functions default=3)
        # Each must have ≥2 params, complexity ≥5, and be unguarded.
        files = {
            "__init__.py": "",
            "core/__init__.py": "",
            "core/engine.py": textwrap.dedent("""\
                def execute(cmd, env, ctx, opts, flags):
                    if cmd:
                        if env:
                            if ctx:
                                if opts:
                                    if flags:
                                        return True
                    return False
            """),
            "core/processor.py": _unguarded_func("process", ["a", "b", "c"], 6),
            "core/validator.py": _unguarded_func("validate", ["x", "y", "z"], 7),
        }
        findings = _run_signal(tmp_path, files, SignalType.GUARD_CLAUSE_DEFICIT)
        nesting_findings = [f for f in findings if "nesting" in f.title.lower()]
        assert len(nesting_findings) >= 1, (
            "Deep nesting (depth 5, threshold 4) should produce nesting finding"
        )
        # Normal: 0.3 + (5-4)*0.15 = 0.45, Mutated gcd_005: 0.9 + 0.15 = 1.05→1.0
        assert nesting_findings[0].score < 0.8, (
            f"Score {nesting_findings[0].score} too high — formula suspect"
        )


# ── MDS: Mutant Duplicates Signal ────────────────────────────────────


class TestMDSThresholds:
    """Kill mds_003, mds_004, mds_005, mds_006."""

    def test_size_ratio_filter(self, tmp_path: Path) -> None:
        """Functions with >3x size difference should NOT match.

        Kills mds_003: mutation changes `< 0.33` to `< 0.01`,
        accepting extreme size mismatches.
        """
        files = {
            "__init__.py": "",
            "small.py": textwrap.dedent("""\
                def process(data):
                    result = []
                    for item in data:
                        if item > 0:
                            result.append(item)
                    return result
            """),
            "big.py": textwrap.dedent("""\
                def process(data):
                    result = []
                    for item in data:
                        if item > 0:
                            result.append(item)
                        elif item == 0:
                            result.append(0)
                        else:
                            result.append(-item)
                    validated = []
                    for r in result:
                        if r is not None:
                            validated.append(r)
                    summary = {}
                    for v in validated:
                        key = str(v)
                        if key not in summary:
                            summary[key] = 0
                        summary[key] += 1
                    output = []
                    for k, v in summary.items():
                        if v > 1:
                            output.append(k)
                    return output
            """),
        }
        findings = _run_signal(tmp_path, files, SignalType.MUTANT_DUPLICATE)
        # Size ratio is very low → should NOT produce MDS finding between these
        dup_findings = [
            f for f in findings
            if "small" in str(f.file_path) or "big" in str(f.file_path)
        ]
        # The mutation would allow matching these despite 4x+ size difference
        assert len(dup_findings) == 0, (
            "Functions with extreme size difference should not match"
        )

    def test_loc_ratio_filter(self, tmp_path: Path) -> None:
        """Functions with >2x LOC difference should NOT match.

        Kills mds_004: mutation changes `< 0.5` to `< 0.01`.
        Uses comment-padded function: identical AST (sim=1.0) but LOC ratio < 0.5.
        Mutation allows comparison → finding produced → assertion fails.
        """
        short_func = textwrap.dedent("""\
            def compute(x, y):
                result = x + y
                if result > 0:
                    return result
                return 0
        """)
        # Same structure, padded with comments to inflate LOC > 2x
        long_func = textwrap.dedent("""\
            def transform(x, y):
                # Initialize computation
                result = x + y
                # Check positivity of the result value
                if result > 0:
                    # Positive: return directly
                    return result
                # Negative or zero: return default
                # This is the fallback path
                # for zero or negative inputs
                # which need a safe return value
                return 0
        """)
        files = {
            "__init__.py": "",
            "module_a.py": short_func,
            "module_b.py": long_func,
        }
        findings = _run_signal(tmp_path, files, SignalType.MUTANT_DUPLICATE)
        # LOC ratio < 0.5 → should be filtered
        # After mutation (< 0.01) they would pass the filter → sim=1.0 → finding
        assert len(findings) == 0, (
            "Functions with >2x LOC difference should be filtered"
        )

    def test_exact_duplicates_produce_findings(self, tmp_path: Path) -> None:
        """Multiple exact duplicate pairs → multiple findings."""
        func_a = textwrap.dedent("""\
            def calculate_total(items, tax_rate):
                total = 0
                for item in items:
                    price = item.get_price()
                    if price > 0:
                        total += price
                    else:
                        total += 0
                return total * (1 + tax_rate)
        """)
        func_b = textwrap.dedent("""\
            def validate_entries(records, threshold):
                valid = []
                for rec in records:
                    value = rec.get_value()
                    if value > threshold:
                        valid.append(rec)
                    elif value == threshold:
                        valid.append(rec)
                return valid
        """)
        files = {"__init__.py": ""}
        # Place exact duplicates in multiple files
        for i in range(4):
            files[f"service_{i}.py"] = func_a + "\n\n" + func_b
        findings = _run_signal(tmp_path, files, SignalType.MUTANT_DUPLICATE)
        assert len(findings) >= 2, (
            f"Expected ≥2 duplicate findings across 4 files, got {len(findings)}"
        )

    def test_near_duplicates_via_phase2(self, tmp_path: Path) -> None:
        """Near-duplicate functions through Phase 2 should produce multiple findings.

        Kills mds_006: mutation changes _MAX_FINDINGS to 1.
        Phase 2 checks _MAX_FINDINGS unlike Phase 1 (exact hash).
        With 4 structurally identical variants (sim=1.0 but different hashes),
        Phase 2 should produce 6 pairwise findings.
        """
        # 4 variants: identical AST structure, different identifiers → sim 1.0
        # body_hash differs → Phase 1 ignores them → Phase 2 compares them.
        variants = [
            textwrap.dedent("""\
                def process_alpha(items, config):
                    results = []
                    for item in items:
                        if item.is_valid():
                            value = item.compute()
                            if value > config.threshold:
                                results.append(value)
                            else:
                                results.append(0)
                    return results
            """),
            textwrap.dedent("""\
                def process_beta(records, settings):
                    output = []
                    for record in records:
                        if record.is_valid():
                            amount = record.compute()
                            if amount > settings.threshold:
                                output.append(amount)
                            else:
                                output.append(0)
                    return output
            """),
            textwrap.dedent("""\
                def process_gamma(entries, options):
                    collected = []
                    for entry in entries:
                        if entry.is_valid():
                            result = entry.compute()
                            if result > options.threshold:
                                collected.append(result)
                            else:
                                collected.append(0)
                    return collected
            """),
            textwrap.dedent("""\
                def process_delta(data, params):
                    values = []
                    for datum in data:
                        if datum.is_valid():
                            score = datum.compute()
                            if score > params.threshold:
                                values.append(score)
                            else:
                                values.append(0)
                    return values
            """),
        ]
        files = {"__init__.py": ""}
        for i, v in enumerate(variants):
            files[f"handler_{i}.py"] = v
        findings = _run_signal(tmp_path, files, SignalType.MUTANT_DUPLICATE)

        # Phase 2 produces 4C2=6 findings for structurally identical pairs.
        # _MAX_FINDINGS=200: all pairs detected; mutation (=1): only first
        assert len(findings) >= 2, (
            f"Expected ≥2 near-duplicate findings from Phase 2, got {len(findings)}"
        )

    def test_severity_medium_for_near_duplicates(self, tmp_path: Path) -> None:
        """Near duplicates (sim 0.80-0.90) should get MEDIUM severity.

        Kills mds_005: mutation changes `sim < 0.9` to `sim < 0.5`,
        which would classify near-duplicates with sim≈0.81 as HIGH.
        """
        # Two long functions: same structure, B has one extra check.
        # Produces sim ≈ 0.81 → MEDIUM.  Mutation (< 0.5): 0.81 ≥ 0.5 → HIGH.
        func_a = textwrap.dedent("""\
            def process_data(items, config):
                results = []
                errors = []
                for item in items:
                    if item.is_valid():
                        value = item.compute()
                        if value > config.threshold:
                            results.append(value)
                        elif value == config.threshold:
                            results.append(value)
                        else:
                            results.append(0)
                    else:
                        errors.append(item)
                if len(results) > 0:
                    average = sum(results) / len(results)
                else:
                    average = 0
                return average
        """)
        func_b = textwrap.dedent("""\
            def transform_data(items, config):
                results = []
                errors = []
                for item in items:
                    if item.is_valid():
                        value = item.compute()
                        if value > config.threshold:
                            results.append(value)
                        elif value == config.threshold:
                            results.append(value)
                        else:
                            results.append(0)
                    else:
                        errors.append(item)
                if len(results) > 0:
                    average = sum(results) / len(results)
                    if average > 100:
                        average = 100
                else:
                    average = 0
                return average
        """)
        files = {
            "__init__.py": "",
            "worker_a.py": func_a,
            "worker_b.py": func_b,
        }
        findings = _run_signal(tmp_path, files, SignalType.MUTANT_DUPLICATE)
        near_dup = [
            f for f in findings
            if f.metadata.get("similarity", 1.0) < 0.9
        ]
        assert len(near_dup) >= 1, (
            f"Expected near-duplicate finding with sim < 0.9, got {len(near_dup)} "
            f"(all findings: {[(f.metadata.get('similarity'), f.severity) for f in findings]})"
        )
        for f in near_dup:
            assert f.severity == Severity.MEDIUM, (
                f"Near-duplicate with sim={f.metadata.get('similarity')} "
                f"should be MEDIUM, got {f.severity}"
            )


# ── PFS: Pattern Fragmentation Signal ────────────────────────────────


class TestPFSThresholds:
    """Kill pfs_001, pfs_002, pfs_004, pfs_005, pfs_006, pfs_007."""

    def test_two_patterns_produces_findings(self, tmp_path: Path) -> None:
        """Module with exactly 2 different error patterns → PFS should fire.

        Kills pfs_004: mutation changes `< 2` to `< 1`.
        """
        files = {
            "handlers/__init__.py": "",
            "handlers/auth.py": textwrap.dedent("""\
                import logging
                logger = logging.getLogger(__name__)

                def login(user, password):
                    try:
                        authenticate(user, password)
                    except Exception as e:
                        logger.error("Login failed: %s", e)
                        raise

                def register(user, email):
                    try:
                        create_account(user, email)
                    except Exception as e:
                        logger.error("Registration failed: %s", e)
                        raise
            """),
            "handlers/payment.py": textwrap.dedent("""\
                def charge(card, amount):
                    try:
                        process_payment(card, amount)
                    except Exception:
                        return None

                def refund(transaction_id, amount):
                    try:
                        process_refund(transaction_id, amount)
                    except Exception:
                        return None
            """),
        }
        findings = _run_signal(
            tmp_path, files, SignalType.PATTERN_FRAGMENTATION,
        )
        pfs = [f for f in findings if "handlers" in str(f.file_path)]
        assert len(pfs) >= 1, (
            "Two different error-handling styles in one module should trigger PFS"
        )

    def test_severity_levels_match_score(self, tmp_path: Path) -> None:
        """PFS findings should have severity consistent with score thresholds.

        Kills pfs_001 (0.7→0.9), pfs_002 (0.5→0.7), pfs_007 (0.3→0.6).
        """
        # Create a module with many fragmented patterns to get varied scores
        files = {
            "workers/__init__.py": "",
            "workers/task_log.py": textwrap.dedent("""\
                import logging
                logger = logging.getLogger(__name__)

                def task_alpha():
                    try:
                        do_alpha()
                    except Exception as e:
                        logger.error("alpha: %s", e)
                        raise

                def task_beta():
                    try:
                        do_beta()
                    except Exception as e:
                        logger.warning("beta: %s", e)
                        raise
            """),
            "workers/task_silent.py": textwrap.dedent("""\
                def task_gamma():
                    try:
                        do_gamma()
                    except Exception:
                        return None

                def task_delta():
                    try:
                        do_delta()
                    except Exception:
                        return {"error": True}
            """),
            "workers/task_bare.py": textwrap.dedent("""\
                def task_epsilon():
                    try:
                        do_epsilon()
                    except:
                        pass

                def task_zeta():
                    try:
                        do_zeta()
                    except:
                        pass
            """),
        }
        findings = _run_signal(
            tmp_path, files, SignalType.PATTERN_FRAGMENTATION,
        )
        for f in findings:
            # Verify severity matches the score thresholds
            if f.score >= 0.7:
                assert f.severity == Severity.HIGH, (
                    f"Score {f.score} should be HIGH, got {f.severity}"
                )
            elif f.score >= 0.5:
                assert f.severity == Severity.MEDIUM, (
                    f"Score {f.score} should be MEDIUM, got {f.severity}"
                )
            elif f.score >= 0.3:
                assert f.severity == Severity.LOW, (
                    f"Score {f.score} should be LOW, got {f.severity}"
                )

    def test_two_variants_medium_severity(self, tmp_path: Path) -> None:
        """Module with exactly 2 error-handling variants → score=0.5, MEDIUM.

        Kills pfs_002: mutation changes MEDIUM threshold from ≥0.5 to ≥0.7.
        With score=0.5, original → MEDIUM; mutated → LOW.
        """
        # Only 2 error handling styles, minimal instances (no spread boost)
        files = {
            "services/__init__.py": "",
            "services/handler_a.py": textwrap.dedent("""\
                import logging
                logger = logging.getLogger(__name__)

                def process_a():
                    try:
                        do_work()
                    except Exception as e:
                        logger.error("fail: %s", e)
                        raise
            """),
            "services/handler_b.py": textwrap.dedent("""\
                def process_b():
                    try:
                        do_work()
                    except Exception:
                        return None
            """),
        }
        findings = _run_signal(
            tmp_path, files, SignalType.PATTERN_FRAGMENTATION,
        )
        pfs = [f for f in findings if "services" in str(f.file_path)]
        assert len(pfs) >= 1, "Two variants should produce PFS finding"
        # 2 variants → frag_score = 1 - 1/2 = 0.5 → MEDIUM
        assert pfs[0].severity == Severity.MEDIUM, (
            f"Expected MEDIUM for 2-variant pattern, got {pfs[0].severity} "
            f"(score={pfs[0].score})"
        )

    def test_spread_boost_crosses_high_boundary(self, tmp_path: Path) -> None:
        """Spread factor boost should push 3-variant score from MEDIUM to HIGH.

        Kills pfs_005: mutation changes ``> 2`` to ``> 20``, disabling boost.
        3 variants → base 0.667.  4 non-canonical → boost 1.08 → 0.72 HIGH.
        Without boost (mutation): 0.667 → MEDIUM.
        """
        _A = textwrap.dedent("""\
            import logging
            logger = logging.getLogger(__name__)
            def {name}():
                try:
                    run()
                except Exception as e:
                    logger.error("{name}: %s", e)
                    raise
        """)
        _B = textwrap.dedent("""\
            def {name}():
                try:
                    run()
                except Exception:
                    return None
        """)
        _C = textwrap.dedent("""\
            def {name}():
                try:
                    run()
                except:
                    pass
        """)
        # 3A (canonical) + 2B + 2C = 7 instances, non_canonical=4
        files = {
            "workers/__init__.py": "",
            "workers/w1.py": _A.format(name="a1") + "\n" + _A.format(name="a2"),
            "workers/w2.py": _A.format(name="a3") + "\n" + _B.format(name="b1"),
            "workers/w3.py": _B.format(name="b2") + "\n" + _C.format(name="c1"),
            "workers/w4.py": _C.format(name="c2"),
        }
        findings = _run_signal(
            tmp_path, files, SignalType.PATTERN_FRAGMENTATION,
        )
        pfs = [f for f in findings if "workers" in str(f.file_path)]
        assert len(pfs) >= 1, "3-variant module with spread boost should trigger PFS"
        # Normal: 0.667 * 1.08 = 0.72 → HIGH
        # Mutation pfs_005 (> 20): no boost → 0.667 → MEDIUM
        assert pfs[0].severity == Severity.HIGH, (
            f"Expected HIGH with spread boost, got {pfs[0].severity} "
            f"(score={pfs[0].score})"
        )

    def test_spread_multiplier_sensitivity(self, tmp_path: Path) -> None:
        """Small spread factor with 3 non-canonical should stay MEDIUM.

        Kills pfs_006: mutation changes multiplier 0.04 → 0.4.
        3 variants, canonical=5, non_canonical=3 → boost 1.04 → 0.694 MEDIUM.
        Mutation: boost 1.4 → 0.934 HIGH.
        """
        _A = textwrap.dedent("""\
            import logging
            logger = logging.getLogger(__name__)
            def {name}():
                try:
                    run()
                except Exception as e:
                    logger.error("{name}: %s", e)
                    raise
        """)
        _B = textwrap.dedent("""\
            def {name}():
                try:
                    run()
                except Exception:
                    return None
        """)
        _C = textwrap.dedent("""\
            def {name}():
                try:
                    run()
                except:
                    pass
        """)
        # 5A (canonical) + 2B + 1C = 8 instances, non_canonical=3
        files = {
            "svc/__init__.py": "",
            "svc/s1.py": _A.format(name="a1") + "\n" + _A.format(name="a2"),
            "svc/s2.py": _A.format(name="a3") + "\n" + _A.format(name="a4"),
            "svc/s3.py": _A.format(name="a5") + "\n" + _B.format(name="b1"),
            "svc/s4.py": _B.format(name="b2") + "\n" + _C.format(name="c1"),
        }
        findings = _run_signal(
            tmp_path, files, SignalType.PATTERN_FRAGMENTATION,
        )
        pfs = [f for f in findings if "svc" in str(f.file_path)]
        assert len(pfs) >= 1, "3-variant module should trigger PFS"
        # Normal: 0.667 * 1.04 = 0.694 → MEDIUM
        # Mutation pfs_006 (0.4): 0.667 * 1.4 = 0.934 → HIGH
        assert pfs[0].severity == Severity.MEDIUM, (
            f"Expected MEDIUM with small spread, got {pfs[0].severity} "
            f"(score={pfs[0].score})"
        )


# ── AVS: Architecture Violation Signal ────────────────────────────────


class TestAVSThresholds:
    """Kill avs_001, avs_002, avs_004."""

    def test_hub_dampening_precision(self, tmp_path: Path) -> None:
        """Hub nodes should be dampened at 90th percentile, not 50th.

        Kills avs_002: mutation changes percentile=0.90 to 0.50.
        With 0.50, many more nodes would be dampened and violations suppressed.

        Kills avs_004: mutation changes AND to OR in hub condition,
        which would include nodes with zero centrality.
        """
        # Create a clear layer violation with explicit boundaries
        files = {
            "__init__.py": "",
            "core/__init__.py": "",
            "utils/__init__.py": "",
            "core/engine.py": (
                "from utils.helpers import helper_a\n"
                "\ndef run():\n    pass\n"
            ),
            "utils/helpers.py": "def helper_a():\n    pass\n",
            "utils/tools.py": "def tool_b():\n    pass\n",
            # Violation: utils importing from core (upward)
            "utils/bridge.py": (
                "from core.engine import run\n"
                "\ndef bridge():\n    run()\n"
            ),
        }
        cfg = DriftConfig(
            include=["**/*.py"],
            exclude=[],
            embeddings_enabled=False,
            policies=PolicyConfig(
                layer_boundaries=[
                    LayerBoundary(
                        name="utils-cannot-import-core",
                        **{"from": "utils/**"},
                        deny_import=["core/**"],
                    ),
                ],
            ),
        )
        findings = _run_signal(
            tmp_path, files, SignalType.ARCHITECTURE_VIOLATION, config=cfg,
        )
        # The upward import from utils→core should be detected
        assert len(findings) >= 1, (
            "Explicit layer boundary violation should trigger AVS"
        )

    def test_hub_nodes_strict_percentile(self) -> None:
        """_compute_hub_nodes at 90th percentile identifies only extreme hubs.

        Kills avs_002: mutation 0.90 → 0.50 would include mid-tier nodes.
        Kills avs_004: AND → OR would include all non-zero centrality nodes.
        """
        g = nx.DiGraph()
        # 10 nodes: 7 sources, 1 hub (8 incoming), 1 mid (4 incoming), 1 low (2 incoming)
        sources = [f"src_{i}" for i in range(7)]
        for s in sources:
            g.add_edge(s, "hub_A")
        g.add_edge("mid_B", "hub_A")       # hub_A total: 8 incoming
        for s in sources[:4]:
            g.add_edge(s, "mid_B")          # mid_B total: 4 incoming
        for s in sources[:2]:
            g.add_edge(s, "low_C")          # low_C total: 2 incoming

        # With default percentile (0.90), only hub_A should be a hub
        hubs = _compute_hub_nodes(g)
        assert "hub_A" in hubs, "Extreme hub must be detected"
        assert "mid_B" not in hubs, (
            "Mid-tier node should NOT be a hub at 90th percentile"
        )
        assert "low_C" not in hubs, (
            "Low-tier node should NOT be a hub at 90th percentile"
        )

    def test_embedding_layer_inference_threshold(self) -> None:
        """Embedding similarity at 0.7 must infer a layer (threshold is 0.5).

        Kills avs_001: mutation 0.5 → 0.99 would reject sim=0.7 and
        return None, leaving files without recognizable directory names
        unclassified — hiding real upward violations.
        """
        emb = MagicMock()
        emb.embed_text.return_value = np.array([1.0, 0.0, 0.0])
        emb.cosine_similarity.return_value = 0.7

        # File in non-standard directory (no layer inference from name)
        pr = ParseResult(
            file_path=Path("mypackage/handler.py"),
            language="python",
            imports=[
                ImportInfo(
                    source_file=Path("mypackage/handler.py"),
                    imported_module="flask",
                    imported_names=[],
                    line_number=1,
                ),
            ],
        )
        proto = {0: np.array([0.9, 0.1, 0.0])}

        layer = _infer_layer_with_embeddings(
            Path("mypackage/handler.py"), pr, emb, proto,
        )
        assert layer == 0, (
            "Embedding with sim=0.7 (above 0.5 threshold) should infer layer 0"
        )
