"""Tests for negative context generation."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from drift.models import (
    Finding,
    NegativeContext,
    NegativeContextCategory,
    NegativeContextScope,
    RepoAnalysis,
    Severity,
    SignalType,
)
from drift.negative_context import (
    _FALLBACK_ONLY_SIGNALS,
    _GENERATORS,
    _neg_id,
    _policy_uncovered_registered_signal_ids,
    _policy_uncovered_signal_types,
    findings_to_negative_context,
    negative_context_to_dict,
)
from drift.output.agent_tasks import analysis_to_agent_tasks, analysis_to_agent_tasks_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
    severity: Severity = Severity.HIGH,
    title: str = "Test finding",
    file_path: str = "services/payment.py",
    metadata: dict | None = None,
    impact: float = 0.6,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=severity,
        score=0.7,
        title=title,
        description="Description of the finding",
        file_path=Path(file_path),
        start_line=10,
        end_line=30,
        related_files=[Path("services/order.py")],
        fix="Apply fix",
        impact=impact,
        metadata=metadata or {},
    )


def _analysis(findings: list[Finding] | None = None) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("/tmp/test-repo"),
        analyzed_at=datetime.datetime(2026, 3, 26, 12, 0, 0),
        drift_score=0.45,
        findings=findings or [],
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestNegativeContextModel:
    def test_create_minimal(self) -> None:
        nc = NegativeContext(
            anti_pattern_id="neg-pfs-abc123",
            category=NegativeContextCategory.ARCHITECTURE,
            source_signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            scope=NegativeContextScope.FILE,
            description="Do not fragment patterns",
            forbidden_pattern="# BAD\ndef foo(): ...",
            canonical_alternative="# GOOD\ndef foo(): ...",
            affected_files=["services/payment.py"],
            confidence=0.85,
            rationale="Pattern fragmentation detected",
        )
        assert nc.anti_pattern_id == "neg-pfs-abc123"
        assert nc.category == NegativeContextCategory.ARCHITECTURE
        assert nc.confidence == 0.85
        assert nc.metadata == {}

    def test_metadata_default_empty(self) -> None:
        nc = NegativeContext(
            anti_pattern_id="test",
            category=NegativeContextCategory.SECURITY,
            source_signal=SignalType.MISSING_AUTHORIZATION,
            severity=Severity.CRITICAL,
            scope=NegativeContextScope.MODULE,
            description="desc",
            forbidden_pattern="bad",
            canonical_alternative="good",
            affected_files=[],
            confidence=0.5,
            rationale="reason",
        )
        assert nc.metadata == {}


class TestNegativeContextEnums:
    def test_category_values(self) -> None:
        assert NegativeContextCategory.SECURITY == "security"
        assert NegativeContextCategory.ARCHITECTURE == "architecture"
        assert NegativeContextCategory.TESTING == "testing"

    def test_scope_values(self) -> None:
        assert NegativeContextScope.FILE == "file"
        assert NegativeContextScope.MODULE == "module"
        assert NegativeContextScope.REPO == "repo"


# ---------------------------------------------------------------------------
# ID determinism
# ---------------------------------------------------------------------------


class TestNegId:
    def test_same_finding_same_id(self) -> None:
        f = _finding()
        id1 = _neg_id(SignalType.PATTERN_FRAGMENTATION, f)
        id2 = _neg_id(SignalType.PATTERN_FRAGMENTATION, f)
        assert id1 == id2

    def test_different_signal_different_id(self) -> None:
        f = _finding()
        id1 = _neg_id(SignalType.PATTERN_FRAGMENTATION, f)
        id2 = _neg_id(SignalType.BROAD_EXCEPTION_MONOCULTURE, f)
        assert id1 != id2

    def test_id_prefix(self) -> None:
        f = _finding()
        nid = _neg_id(SignalType.PATTERN_FRAGMENTATION, f)
        assert nid.startswith("neg-")


# ---------------------------------------------------------------------------
# Generator coverage
# ---------------------------------------------------------------------------


class TestGenerators:
    """Verify every registered generator produces valid NegativeContext items."""

    def test_all_registered_generators_return_list(self) -> None:
        for signal_type, gen_fn in _GENERATORS.items():
            f = _finding(signal_type=signal_type)
            result = gen_fn(f)
            assert isinstance(result, list), f"Generator for {signal_type} must return list"
            for nc in result:
                assert isinstance(nc, NegativeContext), (
                    f"Generator for {signal_type} returned non-NegativeContext"
                )
                assert nc.anti_pattern_id
                assert nc.forbidden_pattern
                assert nc.canonical_alternative
                assert nc.rationale

    def test_tpd_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.TEST_POLARITY_DEFICIT,
            metadata={"function_name": "process_payment"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.category == NegativeContextCategory.TESTING
        assert "process_payment" in nc.description

    def test_hsc_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            severity=Severity.CRITICAL,
            metadata={"secret_type": "API key"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        assert result[0].category == NegativeContextCategory.SECURITY

    def test_maz_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.MISSING_AUTHORIZATION,
            metadata={"endpoint": "/api/admin"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        assert result[0].category == NegativeContextCategory.SECURITY

    def test_bem_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            metadata={"exception_type": "Exception"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        assert result[0].category == NegativeContextCategory.ERROR_HANDLING

    def test_tvs_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            metadata={"module": "services/payments.py", "change_frequency_30d": 12},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.source_signal == SignalType.TEMPORAL_VOLATILITY
        assert nc.metadata.get("fallback_policy") is None

    def test_sms_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            metadata={"expected_contract": "service layer", "actual_behavior": "controller logic"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.source_signal == SignalType.SYSTEM_MISALIGNMENT
        assert "expected" in nc.description.lower()

    def test_tsa_generator(self) -> None:
        f = _finding(
            signal_type=SignalType.TS_ARCHITECTURE,
            metadata={"source": "ui", "target": "infra", "rule": "ui -> infra forbidden"},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.source_signal == SignalType.TS_ARCHITECTURE
        assert "ui" in nc.description
        assert "infra" in nc.description

    def test_signaltype_policy_coverage_is_complete(self) -> None:
        missing = _policy_uncovered_signal_types()
        assert not missing, (
            "NegativeContext policy is incomplete. Missing SignalType entries: "
            f"{sorted(signal.value for signal in missing)}"
        )

    def test_signal_registry_policy_coverage_is_complete(self) -> None:
        missing = _policy_uncovered_registered_signal_ids()
        assert not missing, (
            "NegativeContext policy is incomplete for signal_registry entries. "
            f"Missing signal IDs: {sorted(missing)}"
        )

    def test_fallback_only_policy_is_explicit(self) -> None:
        # Every fallback-only signal must be explicitly declared and enum-valid.
        assert set(SignalType) >= _FALLBACK_ONLY_SIGNALS
        assert _FALLBACK_ONLY_SIGNALS.isdisjoint(_GENERATORS)


# ---------------------------------------------------------------------------
# Public API: findings_to_negative_context
# ---------------------------------------------------------------------------


class TestFindingsToNegativeContext:
    def test_empty_findings(self) -> None:
        result = findings_to_negative_context([])
        assert result == []

    def test_max_items_respected(self) -> None:
        findings = [
            _finding(signal_type=SignalType.PATTERN_FRAGMENTATION, title=f"PFS {i}")
            for i in range(10)
        ]
        result = findings_to_negative_context(findings, max_items=3)
        assert len(result) <= 3

    def test_severity_sorting(self) -> None:
        """Higher-severity contexts should appear first."""
        f_low = _finding(severity=Severity.LOW, title="low")
        f_high = _finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            severity=Severity.HIGH,
            title="high",
        )
        result = findings_to_negative_context([f_low, f_high])
        # Items should be sorted by severity descending
        severities = [nc.severity for nc in result]
        sev_rank = {
            Severity.CRITICAL: 5,
            Severity.HIGH: 4,
            Severity.MEDIUM: 3,
            Severity.LOW: 2,
            Severity.INFO: 1,
        }
        ranks = [sev_rank[s] for s in severities]
        assert ranks == sorted(ranks, reverse=True)

    def test_deduplication(self) -> None:
        """Identical findings should produce deduplicated context."""
        f = _finding()
        result = findings_to_negative_context([f, f])
        ids = [nc.anti_pattern_id for nc in result]
        assert len(ids) == len(set(ids)), "Duplicate IDs found"

    def test_scope_filter(self) -> None:
        f = _finding(signal_type=SignalType.PATTERN_FRAGMENTATION)
        result = findings_to_negative_context([f], scope="file")
        # FILE scope should still include file-level findings
        assert len(result) >= 0  # No crash

    def test_target_file_filter(self) -> None:
        f1 = _finding(file_path="a.py", title="A")
        f2 = _finding(file_path="b.py", title="B")
        result = findings_to_negative_context(
            [f1, f2],
            target_file="a.py",
        )
        for nc in result:
            assert "a.py" in nc.affected_files


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_dict_roundtrip(self) -> None:
        nc = NegativeContext(
            anti_pattern_id="neg-test-123",
            category=NegativeContextCategory.TESTING,
            source_signal=SignalType.TEST_POLARITY_DEFICIT,
            severity=Severity.HIGH,
            scope=NegativeContextScope.FILE,
            description="Test description",
            forbidden_pattern="bad code",
            canonical_alternative="good code",
            affected_files=["test.py"],
            confidence=0.85,
            rationale="reason",
        )
        d = negative_context_to_dict(nc)
        assert d["anti_pattern_id"] == "neg-test-123"
        assert d["category"] == "testing"
        assert d["source_signal"] == "test_polarity_deficit"
        assert d["severity"] == "high"
        assert d["scope"] == "file"
        assert d["confidence"] == 0.85

    def test_dict_is_json_serializable(self) -> None:
        nc = NegativeContext(
            anti_pattern_id="neg-test-456",
            category=NegativeContextCategory.SECURITY,
            source_signal=SignalType.HARDCODED_SECRET,
            severity=Severity.CRITICAL,
            scope=NegativeContextScope.REPO,
            description="No hardcoded secrets",
            forbidden_pattern="API_KEY = 'sk-...'",
            canonical_alternative="API_KEY = os.environ['API_KEY']",
            affected_files=["config.py"],
            confidence=0.95,
            rationale="CWE-798",
        )
        d = negative_context_to_dict(nc)
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["anti_pattern_id"] == "neg-test-456"


# ---------------------------------------------------------------------------
# Integration: AgentTask wiring
# ---------------------------------------------------------------------------


class TestAgentTaskIntegration:
    def test_agent_task_has_negative_context(self) -> None:
        """Tasks generated from findings should have negative_context populated."""
        f = _finding(signal_type=SignalType.TEST_POLARITY_DEFICIT)
        analysis = _analysis([f])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) >= 1
        task = tasks[0]
        assert isinstance(task.negative_context, list)

    def test_agent_tasks_json_includes_negative_context(self) -> None:
        """JSON output should serialize negative_context."""
        f = _finding(signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE)
        analysis = _analysis([f])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        tasks = data["tasks"]
        assert len(tasks) >= 1
        assert "negative_context" in tasks[0]
        assert isinstance(tasks[0]["negative_context"], list)


# ---------------------------------------------------------------------------
# Integration: JSON output includes negative_context
# ---------------------------------------------------------------------------


class TestJsonOutputIntegration:
    def test_json_output_has_negative_context_section(self) -> None:
        from drift.output.json_output import analysis_to_json

        f = _finding(signal_type=SignalType.HARDCODED_SECRET, severity=Severity.CRITICAL)
        analysis = _analysis([f])
        raw = analysis_to_json(analysis)
        data = json.loads(raw)
        assert "negative_context" in data
        assert isinstance(data["negative_context"], list)


# ---------------------------------------------------------------------------
# Phase 3: Project-specific constraint extraction
# ---------------------------------------------------------------------------


class TestAVSProjectSpecific:
    """AVS generator extracts concrete import rules from metadata."""

    def test_uses_src_dst_layers(self) -> None:
        f = _finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "presentation",
                "dst_layer": "infrastructure",
                "rule": "presentation → infrastructure",
            },
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert "presentation" in nc.description
        assert "infrastructure" in nc.description
        assert nc.confidence == 0.90  # higher with explicit rule

    def test_includes_import_path(self) -> None:
        f = _finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "api",
                "dst_layer": "db",
                "import": "db.models",
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "db.models" in nc.forbidden_pattern

    def test_includes_blast_radius(self) -> None:
        f = _finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "core",
                "dst_layer": "utils",
                "blast_radius": 12,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "12" in nc.description
        assert nc.metadata.get("blast_radius") == 12

    def test_includes_instability(self) -> None:
        f = _finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            metadata={
                "src_layer": "api",
                "dst_layer": "core",
                "instability": 0.83,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "0.83" in nc.canonical_alternative
        assert nc.metadata.get("instability") == 0.83


class TestCCCProjectSpecific:
    """CCC generator uses actual co-change pairs from metadata."""

    def test_uses_file_a_b(self) -> None:
        f = _finding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            metadata={
                "file_a": "models.py",
                "file_b": "serializers.py",
                "co_change_weight": 8.5,
                "confidence": 0.92,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "models.py" in nc.description
        assert "serializers.py" in nc.description
        assert "8.5" in nc.description

    def test_commit_samples_in_metadata(self) -> None:
        f = _finding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            metadata={
                "file_a": "a.py",
                "file_b": "b.py",
                "commit_samples": ["abc123", "def456", "ghi789"],
                "confidence": 0.8,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert nc.metadata.get("commit_samples") == ["abc123", "def456", "ghi789"]

    def test_confidence_scales_with_signal(self) -> None:
        f_strong = _finding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            metadata={"confidence": 1.0, "file_a": "a.py", "file_b": "b.py"},
            title="strong",
        )
        f_weak = _finding(
            signal_type=SignalType.CO_CHANGE_COUPLING,
            metadata={"confidence": 0.1, "file_a": "c.py", "file_b": "d.py"},
            title="weak",
        )
        results = findings_to_negative_context([f_strong, f_weak])
        # Strong coupling should have higher NC confidence
        strong_nc = next(r for r in results if "a.py" in r.description)
        weak_nc = next(r for r in results if "c.py" in r.description)
        assert strong_nc.confidence > weak_nc.confidence


class TestECMProjectSpecific:
    """ECM generator extracts concrete exception contracts from metadata."""

    def test_uses_diverged_functions(self) -> None:
        f = _finding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "module": "services.payment",
                "exception_types": ["PaymentError", "ValidationError"],
                "diverged_functions": ["process_refund", "charge_card"],
                "divergence_count": 2,
                "module_function_count": 8,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "process_refund" in nc.description
        assert "2/8" in nc.description
        assert nc.confidence == 0.85  # higher with diverged_fns

    def test_includes_comparison_ref(self) -> None:
        f = _finding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "comparison_ref": "HEAD~5",
                "diverged_functions": ["fetch_data"],
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "HEAD~5" in nc.description

    def test_concrete_forbidden_with_diverged_fn(self) -> None:
        f = _finding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "diverged_functions": ["handle_request"],
                "exception_types": ["AppError"],
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "handle_request" in nc.forbidden_pattern

    def test_exception_count_in_rationale(self) -> None:
        f = _finding(
            signal_type=SignalType.EXCEPTION_CONTRACT_DRIFT,
            metadata={
                "exception_types": ["TypeError", "ValueError", "KeyError"],
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "3 established exception types" in nc.rationale


class TestHSCProjectSpecific:
    """HSC generator uses concrete detection rules from metadata."""

    def test_api_token_rule(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={
                "variable": "OPENAI_KEY",
                "rule_id": "hardcoded_api_token",
                "cwe": "CWE-798",
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "API token" in nc.description
        assert "OPENAI_KEY" in nc.description
        assert "OPENAI_KEY" in nc.forbidden_pattern
        assert nc.metadata["rule_id"] == "hardcoded_api_token"

    def test_placeholder_secret_rule(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={
                "variable": "db_password",
                "rule_id": "placeholder_secret",
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "placeholder" in nc.description.lower()
        assert "changeme" in nc.forbidden_pattern

    def test_uses_variable_key(self) -> None:
        """Phase 3: uses 'variable' metadata key (actual HSC metadata name)."""
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={"variable": "SECRET_TOKEN"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "SECRET_TOKEN" in nc.description

    def test_rule_id_in_rationale(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={"rule_id": "hardcoded_api_token"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "hardcoded_api_token" in nc.rationale


# ---------------------------------------------------------------------------
# Issue #127: Templates use actual code references
# ---------------------------------------------------------------------------


class TestActualCodeReferences:
    """Generators must use actual finding data, not generic template code."""

    def test_hsc_forbidden_uses_actual_variable_name(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={"variable": "EPIC_CLIENT_SECRET"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "EPIC_CLIENT_SECRET" in nc.forbidden_pattern

    def test_hsc_canonical_uses_actual_variable_name(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            metadata={"variable": "STRIPE_KEY"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "STRIPE_KEY" in nc.canonical_alternative

    def test_hsc_includes_file_reference(self) -> None:
        f = _finding(
            signal_type=SignalType.HARDCODED_SECRET,
            file_path="tools/replay_downloader/constants.py",
            metadata={"variable": "EPIC_CLIENT_SECRET"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "constants.py" in nc.forbidden_pattern

    def test_maz_uses_actual_endpoint_name(self) -> None:
        f = _finding(
            signal_type=SignalType.MISSING_AUTHORIZATION,
            metadata={"endpoint": "build_action_packet_legacy"},
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "build_action_packet_legacy" in nc.forbidden_pattern
        assert "build_action_packet_legacy" in nc.canonical_alternative


# ---------------------------------------------------------------------------
# PHR generator (P2: dedicated instead of fallback)
# ---------------------------------------------------------------------------


class TestPhantomReferenceGenerator:
    """P2: PHANTOM_REFERENCE uses a dedicated generator, not fallback."""

    def test_phr_has_dedicated_generator(self) -> None:
        """PHR must be registered, not falling through to _gen_fallback."""
        assert str(SignalType.PHANTOM_REFERENCE) in _GENERATORS

    def test_phr_returns_valid_nc(self) -> None:
        f = _finding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            severity=Severity.MEDIUM,
            title="3 unresolvable references in api/client.py",
            file_path="api/client.py",
            metadata={
                "phantom_names": [
                    {"name": "fetch_remote_config", "line": 15},
                    {"name": "validate_token", "line": 22},
                    {"name": "parse_response", "line": 31},
                ],
                "phantom_count": 3,
            },
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.source_signal == SignalType.PHANTOM_REFERENCE
        assert nc.category == NegativeContextCategory.COMPLETENESS
        assert "client.py" in nc.description
        assert "fetch_remote_config" in nc.description
        assert nc.confidence >= 0.6
        assert nc.metadata.get("fallback_policy") is None

    def test_phr_no_metadata_graceful(self) -> None:
        """PHR finding without metadata still produces valid NC."""
        f = _finding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            severity=Severity.MEDIUM,
            title="Phantom reference in utils.py",
            file_path="utils.py",
            metadata={},
        )
        result = findings_to_negative_context([f])
        assert len(result) >= 1
        nc = result[0]
        assert nc.source_signal == SignalType.PHANTOM_REFERENCE
        assert nc.confidence >= 0.5

    def test_phr_forbidden_pattern_is_specific(self) -> None:
        """Forbidden pattern must reference the actual file, not a generic signal name."""
        f = _finding(
            signal_type=SignalType.PHANTOM_REFERENCE,
            severity=Severity.HIGH,
            file_path="services/auth.py",
            metadata={
                "phantom_names": [{"name": "check_perms", "line": 5}],
                "phantom_count": 1,
            },
        )
        result = findings_to_negative_context([f])
        nc = result[0]
        assert "auth.py" in nc.forbidden_pattern
        assert "ANTI-PATTERN" in nc.forbidden_pattern
