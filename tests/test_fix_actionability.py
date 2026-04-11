"""Fix-text actionability tests.

Validates that drift fix texts are *actionable* — specific enough that
a developer can start working on them today, not generic enough to be
harmless (and therefore useless).

Actionability criteria:
  1. Fix text exists (not None/empty) for every MEDIUM+ finding
  2. Contains at least one *specific reference* (file name, function name,
     number, or concrete technical term) — not just "refactor this"
  3. Contains an *action verb* (remove, add, extract, consolidate, split, ...)
  4. Does NOT rely solely on vague advice ("consider", "review", "think about")
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

# Ensure all signal modules are imported
import drift.signals.architecture_violation  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
from drift.analyzer import analyze_repo
from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import Finding, Severity
from drift.signals.base import AnalysisContext, create_signals

# ---------------------------------------------------------------------------
# Actionability heuristics
# ---------------------------------------------------------------------------

# German + English action verbs that indicate concrete advice
ACTION_VERBS = re.compile(
    r"\b("
    # German
    r"[Kk]onsolidiere|[Ee]ntferne|[Ff]\u00fcge|[Pp]r\u00fcfe|"
    r"[Aa]ufteilen|[Ee]rw\u00e4ge|[Kk]l\u00e4ren|[Ee]rsetze|[Vv]ereinheitliche|"
    r"[Vv]erschiebe|[Aa]nleg[en]|[Ii]mportiere|[Ss]telle\s+sicher|"
    r"[Ee]rstelle|[Hh]inzuf\u00fcgen|[Aa]ktualisiere|[Bb]ehalte|"
    r"[Ee]xtrahiere|[Rr]eduziere|[Ss]tabilisiere|[Ee]rh\u00f6he|"
    r"[Ee]ntkopple|[Uu]ntersuche|[Bb]reche|[Tt]eile|[Ee]rg\u00e4nze|"
    # English
    r"[Rr]emove|[Aa]dd|[Ee]xtract|[Cc]onsolidate|[Ss]plit|[Mm]ove|"
    r"[Rr]efactor|[Rr]eplace|[Ii]ntroduce|[Cc]reate|[Dd]elete|"
    r"[Mm]erge|[Ii]nline|[Ww]rap|[Uu]nify|[Cc]ombine|"
    r"[Dd]ifferentiate|[Cc]atch|[Vv]erify|[Ii]nvestigate|[Dd]ecouple|"
    r"[Rr]oute|[Cc]larify|[Bb]reak|[Ss]tabilize"
    r")\b",
    re.UNICODE,
)

# Patterns that indicate specificity (concrete references)
SPECIFICITY_PATTERNS = [
    re.compile(r"\d+"),  # Contains a number (line, count, complexity)
    re.compile(r"\b[A-Za-z_]\w*\.(py|ts|js|yaml|yml|json|md|toml|cfg)\b"),  # File reference
    re.compile(r"\b[a-z_]\w*\("),  # Function/method reference like func(
    re.compile(
        r"\b(Complexity|Commits?|Authors?|Autoren|Pattern|Docstring|Tests?|"
        r"Return-Type|Import|Dependency|Abhängigkeit|Service\s+Layer|"
        r"Service-Schicht|Interface)\b",
        re.UNICODE,
    ),  # Technical terms
    re.compile(r"[A-Z][a-z]+[A-Z]"),  # CamelCase identifier
    re.compile(r"\b\d+×\b"),  # "3×" pattern count
]

# Vague-only phrases that don't constitute actionable advice
VAGUE_ONLY = re.compile(
    r"^(consider|review|think about|look at|check|maybe|perhaps|möglicherweise|"
    r"eventuell|vielleicht)\b",
    re.IGNORECASE,
)


def _is_actionable(fix: str) -> tuple[bool, list[str]]:
    """Check if a fix text is actionable. Returns (is_actionable, reasons)."""
    issues: list[str] = []

    # Must contain an action verb
    if not ACTION_VERBS.search(fix):
        issues.append("no action verb found")

    # Must contain at least one specific reference
    has_specificity = any(p.search(fix) for p in SPECIFICITY_PATTERNS)
    if not has_specificity:
        issues.append("no specific reference (file, function, number, or technical term)")

    # Must not be only vague advice
    # Strip the action verb and check if the rest is just vague
    sentences = [s.strip() for s in fix.split(".") if s.strip()]
    all_vague = all(VAGUE_ONLY.match(s) for s in sentences)
    if all_vague and sentences:
        issues.append("contains only vague advice without specifics")

    # Minimum length — a 5-word fix can't be specific enough
    if len(fix.split()) < 4:
        issues.append(f"too short ({len(fix.split())} words)")

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Fixtures: generate findings from known code samples
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def self_analysis_findings() -> list[Finding]:
    """Run drift on its own codebase and return all findings."""
    repo_root = Path(__file__).resolve().parent.parent
    config = DriftConfig(
        include=["**/*.py"],
        exclude=[
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.venv*/**",
            "**/.tmp_*venv*/**",
            "**/docs/**",
            "**/tests/**",
            "**/site/**",
        ],
        embeddings_enabled=False,
    )
    analysis = analyze_repo(
        repo_root,
        config=config,
        since_days=365,
        target_path="src/drift",
    )
    return analysis.findings


@pytest.fixture(scope="module")
def deterministic_fixture_findings(tmp_path_factory: pytest.TempPathFactory) -> list[Finding]:
    """Generate deterministic findings from a synthetic codebase with known issues."""
    tmp = tmp_path_factory.mktemp("actionability")

    # Create files that should trigger multiple signals with fix texts
    svc = tmp / "services"
    svc.mkdir()
    (svc / "__init__.py").write_text("")

    # Pattern fragmentation: two different error handling styles
    (svc / "handler_a.py").write_text(
        textwrap.dedent("""\
        def process_order(order_id: str) -> dict:
            try:
                result = lookup(order_id)
                return {"status": "ok", "data": result}
            except ValueError as e:
                raise OrderError(str(e)) from e

        class OrderError(Exception):
            pass

        def lookup(oid: str) -> dict:
            return {"id": oid}
    """)
    )
    (svc / "handler_b.py").write_text(
        textwrap.dedent("""\
        def process_refund(refund_id):
            try:
                result = find_refund(refund_id)
                return result
            except Exception as e:
                print(f"Error: {e}")
                return None

        def find_refund(rid):
            return {"id": rid}
    """)
    )

    # Explainability deficit: complex function without docs
    (svc / "complex_logic.py").write_text(
        textwrap.dedent("""\
        def calculate_risk_score(transactions, user_profile, market_data,
                                 seasonal_factors=None, override_rules=None):
            score = 0.0
            for tx in transactions:
                if tx.get("amount", 0) > 10000:
                    if user_profile.get("tier") == "premium":
                        score += 0.1
                    else:
                        score += 0.5
                        if market_data.get("volatility", 0) > 0.8:
                            score += 0.3
                            if seasonal_factors:
                                for sf in seasonal_factors:
                                    if sf > 0.5:
                                        score *= 1.1
                                    elif sf < 0.2:
                                        score *= 0.9
                if override_rules:
                    for rule in override_rules:
                        if rule.get("type") == "cap":
                            score = min(score, rule["value"])
                        elif rule.get("type") == "floor":
                            score = max(score, rule["value"])
            return min(max(score, 0.0), 1.0)
    """)
    )

    # Parse and run signals
    config = DriftConfig(
        include=["**/*.py"],
        exclude=["**/__pycache__/**"],
        embeddings_enabled=False,
    )
    files = discover_files(tmp, config.include, config.exclude)
    parse_results = [parse_file(f.path, tmp, f.language) for f in files]

    import datetime

    from drift.models import FileHistory

    file_histories: dict[str, FileHistory] = {}
    for finfo in files:
        key = finfo.path.as_posix()
        file_histories[key] = FileHistory(
            path=finfo.path,
            total_commits=5,
            unique_authors=2,
            ai_attributed_commits=0,
            change_frequency_30d=1.0,
            defect_correlated_commits=0,
            last_modified=datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=10),
            first_seen=datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=90),
        )

    ctx = AnalysisContext(
        repo_path=tmp,
        config=config,
        parse_results=parse_results,
        file_histories=file_histories,
        embedding_service=None,
    )

    signals = create_signals(ctx)
    all_findings: list[Finding] = []
    for signal in signals:
        try:
            findings = signal.analyze(parse_results, file_histories, config)
            all_findings.extend(findings)
        except Exception:
            pass

    return all_findings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFixTextPresence:
    """Every MEDIUM+ finding must have a non-empty fix text."""

    def test_medium_plus_findings_have_fix(
        self, deterministic_fixture_findings: list[Finding]
    ) -> None:
        """All MEDIUM+ findings from deterministic fixtures must have fix text."""
        medium_plus = [
            f
            for f in deterministic_fixture_findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM)
        ]
        # Deterministic fixture: no findings means a regression in signal setup.
        assert medium_plus, "Deterministic fixture produced no MEDIUM+ findings"

        missing_fix = [f for f in medium_plus if not f.fix]
        assert not missing_fix, (
            f"{len(missing_fix)}/{len(medium_plus)} MEDIUM+ findings lack fix text:\n"
            + "\n".join(f"  [{f.signal_type}] {f.title}" for f in missing_fix[:10])
        )

    @pytest.mark.slow
    def test_self_analysis_fix_coverage(self, self_analysis_findings: list[Finding]) -> None:
        """Optional self-analysis health-check: >=80% of findings should have fix text."""
        if not self_analysis_findings:
            pytest.skip("No self-analysis findings")

        with_fix = [f for f in self_analysis_findings if f.fix]
        coverage = len(with_fix) / len(self_analysis_findings)
        assert coverage >= 0.8, (
            f"Fix text coverage {coverage:.0%} < 80% "
            f"({len(with_fix)}/{len(self_analysis_findings)})"
        )


class TestFixTextActionability:
    """Fix texts must be specific and actionable, not generic advice."""

    def test_fixture_fixes_are_actionable(
        self, deterministic_fixture_findings: list[Finding]
    ) -> None:
        """Every fix text from deterministic fixtures must pass actionability check."""
        findings_with_fix = [f for f in deterministic_fixture_findings if f.fix]
        # Deterministic fixture: missing fix texts indicates a regression.
        assert findings_with_fix, "Deterministic fixture produced no findings with fix text"

        failures = []
        for f in findings_with_fix:
            is_ok, issues = _is_actionable(f.fix)
            if not is_ok:
                failures.append(
                    f"  [{f.signal_type}] {f.title}\n"
                    f"    Fix: {f.fix[:100]}\n"
                    f"    Issues: {', '.join(issues)}"
                )

        assert not failures, (
            f"{len(failures)}/{len(findings_with_fix)} fix texts are not actionable:\n"
            + "\n".join(failures[:10])
        )

    @pytest.mark.slow
    def test_self_analysis_actionability_rate(self, self_analysis_findings: list[Finding]) -> None:
        """Optional self-analysis health-check: >=90% of fix texts should be actionable.

        Baseline (2026-03): 76%. Achieved (2026-03): 100%.
        Track this metric over time — improving fix-text quality directly
        impacts customer trust.
        """
        with_fix = [f for f in self_analysis_findings if f.fix]
        if not with_fix:
            pytest.skip("No findings with fix text in self-analysis")

        actionable_count = sum(1 for f in with_fix if _is_actionable(f.fix)[0])
        rate = actionable_count / len(with_fix)
        assert rate >= 0.90, (
            f"Actionability rate {rate:.0%} < 90% ({actionable_count}/{len(with_fix)})"
        )

    def test_no_fix_is_purely_vague(self, deterministic_fixture_findings: list[Finding]) -> None:
        """No fix text should consist entirely of vague advice."""
        vague_fixes = []
        for f in deterministic_fixture_findings:
            if not f.fix:
                continue
            sentences = [s.strip() for s in f.fix.split(".") if s.strip()]
            if sentences and all(VAGUE_ONLY.match(s) for s in sentences):
                vague_fixes.append(f"  [{f.signal_type}] Fix: {f.fix}")

        assert not vague_fixes, f"{len(vague_fixes)} fix text(s) are purely vague:\n" + "\n".join(
            vague_fixes[:5]
        )


class TestFixTextSpecificity:
    """Fix texts must contain concrete references, not just templates."""

    def test_fixes_contain_identifiers(self, deterministic_fixture_findings: list[Finding]) -> None:
        """Fix texts should reference specific files, functions, or counts."""
        with_fix = [f for f in deterministic_fixture_findings if f.fix]
        # Deterministic fixture: no findings with fix text is a hard failure.
        assert with_fix, "Deterministic fixture produced no findings with fix text"

        generic = []
        for f in with_fix:
            has_specificity = any(p.search(f.fix) for p in SPECIFICITY_PATTERNS)
            if not has_specificity:
                generic.append(f"  [{f.signal_type}] {f.title}\n    Fix: {f.fix[:120]}")

        assert not generic, (
            f"{len(generic)}/{len(with_fix)} fix texts lack specific references:\n"
            + "\n".join(generic[:10])
        )

    @pytest.mark.slow
    def test_actionability_report(self, self_analysis_findings: list[Finding]) -> None:
        """Print actionability breakdown for manual review (always passes)."""
        with_fix = [f for f in self_analysis_findings if f.fix]
        if not with_fix:
            return

        actionable = 0
        issues_summary: dict[str, int] = {}
        for f in with_fix:
            is_ok, issues = _is_actionable(f.fix)
            if is_ok:
                actionable += 1
            for issue in issues:
                issues_summary[issue] = issues_summary.get(issue, 0) + 1

        total = len(self_analysis_findings)
        with_fix_count = len(with_fix)

        print(f"\n{'=' * 60}")
        print("Fix-Text Actionability Report (Self-Analysis)")
        print(f"{'=' * 60}")
        print(f"  Total findings:     {total}")
        print(f"  With fix text:      {with_fix_count} ({with_fix_count / total:.0%})")
        print(f"  Actionable:         {actionable} ({actionable / with_fix_count:.0%})")
        if issues_summary:
            print("\n  Common issues:")
            for issue, count in sorted(issues_summary.items(), key=lambda x: -x[1]):
                print(f"    {issue}: {count}")
