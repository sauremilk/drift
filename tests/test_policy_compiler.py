"""Unit tests for policy_compiler — pure-logic functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from drift.models._policy import CompiledPolicy, PolicyRule
from drift.policy_compiler import (
    CompileScope,
    _build_risk_context,
    _extract_top_signals,
    _in_scope,
    _paths_to_modules,
    assemble_rules,
    compile_calibration_rules,
    compile_finding_rules,
    compile_policy,
    compile_scope_rules,
    render_policy_markdown,
    resolve_compile_scope,
)

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestPolicyRule:
    def test_to_dict_roundtrip(self):
        rule = PolicyRule(
            id="test-001",
            category="prohibition",
            rule="Do not do X.",
            enforcement="block",
            source="ADR-001",
            confidence=0.9,
        )
        d = rule.to_dict()
        assert d["id"] == "test-001"
        assert d["category"] == "prohibition"
        assert d["enforcement"] == "block"
        assert d["source"] == "ADR-001"
        assert d["confidence"] == 0.9

    def test_defaults(self):
        rule = PolicyRule(id="x", category="scope", rule="text")
        assert rule.enforcement == "warn"
        assert rule.source is None
        assert rule.confidence == 1.0


class TestCompiledPolicy:
    def test_to_dict(self):
        rule = PolicyRule(id="r1", category="scope", rule="Scope rule.")
        policy = CompiledPolicy(
            task="test task",
            scope={"allowed_paths": ["src/"]},
            rules=[rule],
            reuse_targets=[],
            risk_context={"finding_count": 0},
        )
        d = policy.to_dict()
        assert d["task"] == "test task"
        assert len(d["rules"]) == 1
        assert d["rules"][0]["id"] == "r1"
        assert "compiled_at" in d


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestPathsToModules:
    def test_simple_paths(self):
        result = _paths_to_modules(["src/drift/signals/foo.py", "src/drift/api/bar.py"])
        assert "src/drift/signals" in result
        assert "src/drift/api" in result

    def test_short_paths(self):
        result = _paths_to_modules(["src/foo.py"])
        assert "src/foo.py" in result

    def test_single_segment(self):
        result = _paths_to_modules(["README.md"])
        assert "README.md" in result

    def test_backslash_normalisation(self):
        result = _paths_to_modules(["src\\drift\\models\\file.py"])
        assert "src/drift/models" in result

    def test_empty(self):
        assert _paths_to_modules([]) == []


class TestInScope:
    def test_empty_scope_matches_everything(self):
        scope = CompileScope()
        assert _in_scope("src/drift/foo.py", scope) is True

    def test_allowed_path_matches(self):
        scope = CompileScope(allowed_paths=["src/drift/signals"])
        assert _in_scope("src/drift/signals/avs.py", scope) is True

    def test_unrelated_path_no_match(self):
        scope = CompileScope(allowed_paths=["src/drift/signals"])
        assert _in_scope("tests/fixtures/foo.py", scope) is False

    def test_module_match(self):
        scope = CompileScope(affected_modules=["src/drift/api"])
        assert _in_scope("src/drift/api", scope) is True


class TestExtractTopSignals:
    def test_empty_findings(self):
        assert _extract_top_signals(None) == []
        assert _extract_top_signals([]) == []

    def test_extracts_top(self):
        finding = MagicMock()
        finding.signal_type = "AVS"
        result = _extract_top_signals([finding, finding])
        assert result == ["AVS"]


class TestBuildRiskContext:
    def test_empty(self):
        ctx = _build_risk_context([])
        assert ctx["finding_count"] == 0
        assert ctx["top_signal"] is None

    def test_with_findings(self):
        f1 = MagicMock()
        f1.signal_type = "AVS"
        f1.severity = "high"
        f2 = MagicMock()
        f2.signal_type = "AVS"
        f2.severity = "medium"
        ctx = _build_risk_context([f1, f2])
        assert ctx["finding_count"] == 2
        assert ctx["top_signal"] == "AVS"


# ---------------------------------------------------------------------------
# Rule generator tests
# ---------------------------------------------------------------------------

class TestCompileScopeRules:
    def test_forbidden_paths_generate_block_rules(self):
        scope = CompileScope(forbidden_paths=["tests/", "docs/"])
        rules = compile_scope_rules(scope)
        block_rules = [r for r in rules if r.enforcement == "block"]
        assert len(block_rules) == 2
        assert all(r.category == "scope" for r in block_rules)

    def test_allowed_paths_generate_warn_rule(self):
        scope = CompileScope(allowed_paths=["src/drift/api/scan.py"])
        rules = compile_scope_rules(scope)
        assert any(r.id == "scope-boundary" for r in rules)

    def test_empty_scope_no_rules(self):
        scope = CompileScope()
        rules = compile_scope_rules(scope)
        assert rules == []


class TestCompileCalibrationRules:
    def test_no_confidence_returns_empty(self):
        rules = compile_calibration_rules(None, None, ["AVS"])
        assert rules == []

    def test_low_confidence_generates_rule(self):
        rules = compile_calibration_rules(
            calibration_weights=None,
            calibration_confidence={"AVS": 0.3, "EDS": 0.8},
            top_signals=["AVS", "EDS"],
        )
        assert len(rules) == 1
        assert rules[0].id == "cal-low-conf-AVS"
        assert rules[0].category == "review_trigger"

    def test_high_confidence_no_rule(self):
        rules = compile_calibration_rules(
            calibration_weights=None,
            calibration_confidence={"AVS": 0.9},
            top_signals=["AVS"],
        )
        assert rules == []


class TestCompileFindingRules:
    def test_empty(self):
        assert compile_finding_rules([]) == []

    def test_generates_stop_conditions(self):
        f1 = MagicMock()
        f1.signal_type = "EDS"
        f2 = MagicMock()
        f2.signal_type = "EDS"
        rules = compile_finding_rules([f1, f2])
        assert len(rules) == 1
        assert rules[0].category == "stop_condition"
        assert "2 existing EDS" in rules[0].rule


# ---------------------------------------------------------------------------
# Assembly tests
# ---------------------------------------------------------------------------

class TestAssembleRules:
    def test_deduplication(self):
        r1 = PolicyRule(id="a", category="scope", rule="Same rule.")
        r2 = PolicyRule(id="b", category="scope", rule="Same rule.")
        result = assemble_rules([r1, r2])
        assert len(result) == 1

    def test_enforcement_priority(self):
        r_block = PolicyRule(id="a", category="prohibition", rule="Block", enforcement="block")
        r_info = PolicyRule(id="b", category="reuse", rule="Info", enforcement="info")
        r_warn = PolicyRule(id="c", category="scope", rule="Warn", enforcement="warn")
        result = assemble_rules([r_info, r_block, r_warn])
        assert result[0].enforcement == "block"
        assert result[1].enforcement == "warn"
        assert result[2].enforcement == "info"

    def test_max_rules_cap(self):
        rules = [
            PolicyRule(id=f"r{i}", category="scope", rule=f"Rule {i}")
            for i in range(20)
        ]
        result = assemble_rules(rules, max_rules=5)
        assert len(result) <= 5

    def test_max_per_category_cap(self):
        rules = [
            PolicyRule(id=f"s{i}", category="scope", rule=f"Scope rule {i}")
            for i in range(10)
        ]
        result = assemble_rules(rules, max_per_category=3)
        scope_count = sum(1 for r in result if r.category == "scope")
        assert scope_count <= 3


# ---------------------------------------------------------------------------
# Markdown rendering tests
# ---------------------------------------------------------------------------

class TestRenderPolicyMarkdown:
    def test_renders_task_header(self):
        policy = CompiledPolicy(task="Add logging to ingestion")
        md = render_policy_markdown(policy)
        assert "Add logging to ingestion" in md

    def test_renders_rules_by_category(self):
        rules = [
            PolicyRule(
                id="p1", category="prohibition", rule="No touching config.", enforcement="block"
            ),
            PolicyRule(id="s1", category="scope", rule="Stay in src/drift/.", enforcement="warn"),
        ]
        policy = CompiledPolicy(task="test", rules=rules)
        md = render_policy_markdown(policy)
        assert "Prohibitions" in md
        assert "Scope Boundaries" in md
        assert "[BLOCK]" in md

    def test_renders_reuse_targets(self):
        policy = CompiledPolicy(
            task="test",
            reuse_targets=[{
                "symbol": "BaseSignal",
                "kind": "class",
                "module_path": "src/drift/signals",
                "usage_count": 12,
            }],
        )
        md = render_policy_markdown(policy)
        assert "BaseSignal" in md

    def test_renders_risk_context(self):
        policy = CompiledPolicy(
            task="test",
            risk_context={"finding_count": 5, "top_signal": "AVS"},
        )
        md = render_policy_markdown(policy)
        assert "5 existing findings" in md


# ---------------------------------------------------------------------------
# Scope resolution tests
# ---------------------------------------------------------------------------

class TestResolveCompileScope:
    def test_git_diff_paths(self, tmp_path: Path):
        scope = resolve_compile_scope(
            "fix bug",
            tmp_path,
            git_diff_paths=["src/drift/api/scan.py", "tests/test_scan.py"],
        )
        assert "src/drift/api/scan.py" in scope.allowed_paths
        assert len(scope.affected_modules) > 0

    def test_empty_inputs_returns_empty_scope(self, tmp_path: Path):
        scope = resolve_compile_scope("unknown task", tmp_path)
        # Empty scope is valid — means "whole repo"
        assert isinstance(scope, CompileScope)


# ---------------------------------------------------------------------------
# Top-level compile_policy tests
# ---------------------------------------------------------------------------

class TestCompilePolicy:
    def test_compiles_with_git_diff(self, tmp_path: Path):
        policy = compile_policy(
            "refactor scoring",
            tmp_path,
            git_diff_paths=["src/drift/scoring/engine.py"],
        )
        assert isinstance(policy, CompiledPolicy)
        assert policy.task == "refactor scoring"
        assert len(policy.agent_instruction) > 0

    def test_compiles_with_empty_inputs(self, tmp_path: Path):
        policy = compile_policy("unknown task", tmp_path)
        assert isinstance(policy, CompiledPolicy)

    def test_max_rules_respected(self, tmp_path: Path):
        policy = compile_policy(
            "big task",
            tmp_path,
            git_diff_paths=[f"src/drift/module{i}/file.py" for i in range(20)],
            max_rules=3,
        )
        assert len(policy.rules) <= 3

    def test_calibration_data_integrated(self, tmp_path: Path):
        policy = compile_policy(
            "fix low-confidence signal",
            tmp_path,
            git_diff_paths=["src/drift/signals/avs.py"],
            calibration_confidence={"AVS": 0.2},
            scoped_findings=[MagicMock(signal_type="AVS", severity="high")],
        )
        # Should have a calibration review_trigger rule
        cal_rules = [r for r in policy.rules if r.id.startswith("cal-")]
        assert len(cal_rules) == 1

    def test_to_dict_serialisable(self, tmp_path: Path):
        """CompiledPolicy.to_dict() must be JSON-safe."""
        import json

        policy = compile_policy("test", tmp_path, git_diff_paths=["src/drift/api/scan.py"])
        d = policy.to_dict()
        # Should not raise
        json.dumps(d, default=str)
