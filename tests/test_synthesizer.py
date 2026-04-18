"""Tests for the Skill Synthesizer module."""

from __future__ import annotations

import json

import pytest

from drift.calibration.feedback import FeedbackEvent
from drift.calibration.history import FindingSnapshot, ScanSnapshot
from drift.synthesizer._cluster import (
    _compute_trend,
    _resolve_module_path,
    _stable_dir,
    build_finding_clusters,
)
from drift.synthesizer._draft_generator import (
    _compute_draft_confidence,
    _to_kebab,
    generate_skill_drafts,
)
from drift.synthesizer._effectiveness import (
    create_effectiveness_baseline,
    load_effectiveness_records,
    save_effectiveness_record,
    update_effectiveness,
)
from drift.synthesizer._models import (
    ClusterFeedback,
    FindingCluster,
    SkillDraft,
    SkillEffectivenessRecord,
    TriageDecision,
    _compute_cluster_id,
)
from drift.synthesizer._triage import (
    _compute_overlap,
    _list_existing_skills,
    triage_skill_drafts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    signal_type: str = "pattern_fragmentation",
    file_path: str = "src/drift/signals/pfs.py",
    score: float = 0.7,
) -> FindingSnapshot:
    return FindingSnapshot(
        signal_type=signal_type,
        file_path=file_path,
        score=score,
        start_line=10,
    )


def _make_snapshot(
    findings: list[FindingSnapshot] | None = None,
    timestamp: str = "2025-01-01T00:00:00+00:00",
) -> ScanSnapshot:
    return ScanSnapshot(
        timestamp=timestamp,
        drift_score=5.0,
        finding_count=len(findings) if findings else 0,
        findings=findings or [],
    )


def _make_cluster(
    signal_type: str = "pattern_fragmentation",
    module_path: str = "src/drift/signals",
    occurrence_count: int = 5,
    recurrence_rate: float = 0.8,
    trend: str = "stable",
    feedback: ClusterFeedback | None = None,
) -> FindingCluster:
    return FindingCluster(
        cluster_id=_compute_cluster_id(signal_type, module_path, None),
        signal_type=signal_type,
        rule_id=None,
        module_path=module_path,
        affected_files=["src/drift/signals/pfs.py"],
        occurrence_count=occurrence_count,
        recurrence_rate=recurrence_rate,
        first_seen="2025-01-01T00:00:00+00:00",
        last_seen="2025-01-05T00:00:00+00:00",
        trend=trend,
        feedback=feedback or ClusterFeedback(),
    )


# ===========================================================================
# Models
# ===========================================================================


class TestClusterFeedback:
    def test_precision_no_data(self):
        fb = ClusterFeedback()
        assert fb.precision == 1.0

    def test_precision_with_data(self):
        fb = ClusterFeedback(tp=8, fp=2, fn=0)
        assert fb.precision == pytest.approx(0.8)

    def test_recall_with_data(self):
        fb = ClusterFeedback(tp=8, fp=0, fn=2)
        assert fb.recall == pytest.approx(0.8)

    def test_total(self):
        fb = ClusterFeedback(tp=3, fp=2, fn=1)
        assert fb.total == 6

    def test_to_dict(self):
        fb = ClusterFeedback(tp=1, fp=2, fn=3)
        assert fb.to_dict() == {"tp": 1, "fp": 2, "fn": 3}


class TestComputeClusterId:
    def test_deterministic(self):
        a = _compute_cluster_id("pfs", "src/drift", None)
        b = _compute_cluster_id("pfs", "src/drift", None)
        assert a == b
        assert len(a) == 16

    def test_different_inputs(self):
        a = _compute_cluster_id("pfs", "src/drift", None)
        b = _compute_cluster_id("avs", "src/drift", None)
        assert a != b


class TestFindingCluster:
    def test_to_dict_roundtrip(self):
        cluster = _make_cluster()
        d = cluster.to_dict()
        assert d["signal_type"] == "pattern_fragmentation"
        assert d["recurrence_rate"] == 0.8
        assert isinstance(d["feedback"], dict)


class TestSkillDraft:
    def test_to_dict(self):
        cluster = _make_cluster()
        draft = SkillDraft(
            kind="guard",
            name="guard-src-drift-signals",
            module_path="src/drift/signals",
            trigger="Test trigger",
            goal="Test goal",
            trigger_signals=["PFS"],
            constraints=[],
            negative_examples=[],
            fix_patterns=[],
            verify_commands=["drift nudge"],
            source_cluster=cluster,
            confidence=0.85,
        )
        d = draft.to_dict()
        assert d["kind"] == "guard"
        assert d["confidence"] == 0.85


class TestTriageDecision:
    def test_to_dict(self):
        cluster = _make_cluster()
        draft = SkillDraft(
            kind="guard",
            name="guard-test",
            module_path="src/test",
            trigger="t",
            goal="g",
            trigger_signals=["PFS"],
            constraints=[],
            negative_examples=[],
            fix_patterns=[],
            verify_commands=[],
            source_cluster=cluster,
            confidence=0.7,
        )
        decision = TriageDecision(
            draft=draft,
            action="new",
            merge_target=None,
            reason="No overlap",
            sprawl_risk=False,
        )
        d = decision.to_dict()
        assert d["action"] == "new"
        assert d["sprawl_risk"] is False


class TestSkillEffectivenessRecord:
    def test_effectiveness_insufficient_data(self):
        rec = SkillEffectivenessRecord(
            skill_name="test",
            created_at="2025-01-01",
            cluster_id="abc",
            pre_recurrence_rate=0.8,
            post_recurrence_rate=None,
            scans_since_creation=1,
        )
        assert rec.effectiveness is None

    def test_effectiveness_computed(self):
        rec = SkillEffectivenessRecord(
            skill_name="test",
            created_at="2025-01-01",
            cluster_id="abc",
            pre_recurrence_rate=0.8,
            post_recurrence_rate=0.4,
            scans_since_creation=5,
        )
        assert rec.effectiveness == pytest.approx(0.5)

    def test_effectiveness_zero_pre(self):
        rec = SkillEffectivenessRecord(
            skill_name="test",
            created_at="2025-01-01",
            cluster_id="abc",
            pre_recurrence_rate=0.0,
            post_recurrence_rate=0.0,
            scans_since_creation=5,
        )
        assert rec.effectiveness == 0.0


# ===========================================================================
# Cluster Engine
# ===========================================================================


class TestStableDir:
    def test_posix(self):
        assert _stable_dir("src/drift/signals/pfs.py") == "src/drift/signals"

    def test_root(self):
        assert _stable_dir("file.py") == "."


class TestResolveModulePath:
    def test_no_known_modules(self):
        assert _resolve_module_path("src/drift/signals") == "src/drift/signals"

    def test_longest_prefix(self):
        known = ["src/drift", "src/drift/signals", "src"]
        assert _resolve_module_path("src/drift/signals", known) == "src/drift/signals"

    def test_fallback(self):
        known = ["src/other"]
        assert _resolve_module_path("src/drift/signals", known) == "src/drift/signals"


class TestComputeTrend:
    def test_single_value(self):
        assert _compute_trend([5.0]) == "stable"

    def test_degrading(self):
        assert _compute_trend([1.0, 1.0, 3.0, 4.0]) == "degrading"

    def test_improving(self):
        assert _compute_trend([4.0, 3.0, 1.0, 1.0]) == "improving"

    def test_stable(self):
        assert _compute_trend([2.0, 2.0, 2.0, 2.0]) == "stable"


class TestBuildFindingClusters:
    def test_empty_snapshots(self):
        assert build_finding_clusters([]) == []

    def test_below_threshold(self):
        """A single occurrence should not form a cluster."""
        findings = [_make_finding()]
        snapshot = _make_snapshot(findings)
        clusters = build_finding_clusters([snapshot])
        assert len(clusters) == 0

    def test_recurring_findings_cluster(self):
        """Findings appearing in multiple scans should form a cluster."""
        finding = _make_finding()
        snapshots = [
            _make_snapshot([finding], f"2025-01-0{i}T00:00:00+00:00")
            for i in range(1, 6)
        ]
        clusters = build_finding_clusters(
            snapshots, min_recurrence=3, min_recurrence_rate=0.5,
        )
        assert len(clusters) == 1
        assert clusters[0].occurrence_count == 5
        assert clusters[0].recurrence_rate == 1.0

    def test_feedback_enrichment(self):
        """Feedback events should enrich cluster feedback counts."""
        finding = _make_finding()
        snapshots = [_make_snapshot([finding]) for _ in range(5)]
        feedback = [
            FeedbackEvent(
                signal_type="pattern_fragmentation",
                file_path="src/drift/signals/pfs.py",
                verdict="tp",
                source="manual",
            ),
            FeedbackEvent(
                signal_type="pattern_fragmentation",
                file_path="src/drift/signals/pfs.py",
                verdict="fp",
                source="manual",
            ),
        ]
        clusters = build_finding_clusters(
            snapshots, feedback, min_recurrence=3, min_recurrence_rate=0.5,
        )
        assert len(clusters) == 1
        assert clusters[0].feedback.tp == 1
        assert clusters[0].feedback.fp == 1


# ===========================================================================
# Draft Generator
# ===========================================================================


class TestToKebab:
    def test_simple(self):
        assert _to_kebab("src/drift/signals") == "src-drift-signals"

    def test_underscores(self):
        assert _to_kebab("src/drift/arch_graph") == "src-drift-arch-graph"


class TestComputeDraftConfidence:
    def test_base_confidence(self):
        cluster = _make_cluster(recurrence_rate=1.0)
        conf = _compute_draft_confidence(cluster, None)
        assert 0.7 < conf < 0.9

    def test_degrading_boost(self):
        cluster = _make_cluster(recurrence_rate=1.0, trend="degrading")
        conf = _compute_draft_confidence(cluster, None)
        assert conf >= 0.8


class TestGenerateSkillDrafts:
    def test_empty_clusters(self):
        assert generate_skill_drafts([]) == []

    def test_guard_and_repair_generated(self):
        cluster = _make_cluster()
        drafts = generate_skill_drafts([cluster], kinds="all")
        kinds = {d.kind for d in drafts}
        assert "guard" in kinds
        assert "repair" in kinds

    def test_guard_only(self):
        cluster = _make_cluster()
        drafts = generate_skill_drafts([cluster], kinds="guard")
        assert all(d.kind == "guard" for d in drafts)

    def test_repair_only(self):
        cluster = _make_cluster()
        drafts = generate_skill_drafts([cluster], kinds="repair")
        assert all(d.kind == "repair" for d in drafts)

    def test_draft_names_are_kebab(self):
        cluster = _make_cluster(module_path="src/drift/signals")
        drafts = generate_skill_drafts([cluster])
        for d in drafts:
            assert "_" not in d.name
            assert "/" not in d.name

    def test_negative_examples_from_fp_feedback(self):
        fb = ClusterFeedback(tp=5, fp=3, fn=0)
        cluster = _make_cluster(feedback=fb)
        drafts = generate_skill_drafts([cluster])
        # At least one draft should have negative examples
        has_negatives = any(d.negative_examples for d in drafts)
        assert has_negatives


# ===========================================================================
# Triage Engine
# ===========================================================================


class TestComputeOverlap:
    def test_no_overlap(self):
        score = _compute_overlap(["PFS"], "src/drift/signals", "other-skill", ["AVS"])
        assert score < 0.3

    def test_signal_overlap(self):
        score = _compute_overlap(["PFS"], "src/drift/signals", "guard-pfs", ["PFS"])
        assert score > 0.0

    def test_module_overlap(self):
        score = _compute_overlap(
            ["PFS"], "src/drift/signals", "guard-src-drift-signals", ["PFS"],
        )
        assert score > 0.5


class TestListExistingSkills:
    def test_no_skills_dir(self, tmp_path):
        result = _list_existing_skills(tmp_path)
        assert result == {}

    def test_finds_skills(self, tmp_path):
        skills_dir = tmp_path / ".github" / "skills" / "guard-test"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "# Guard\n\nAktiv bei Signalen: AVS, PFS\n", encoding="utf-8",
        )
        result = _list_existing_skills(tmp_path)
        assert "guard-test" in result
        assert "AVS" in result["guard-test"]
        assert "PFS" in result["guard-test"]


class TestTriageSkillDrafts:
    def test_empty_drafts(self):
        assert triage_skill_drafts([]) == []

    def test_low_confidence_discard(self):
        cluster = _make_cluster()
        draft = SkillDraft(
            kind="guard",
            name="guard-test",
            module_path="src/test",
            trigger="t",
            goal="g",
            trigger_signals=["PFS"],
            constraints=[],
            negative_examples=[],
            fix_patterns=[],
            verify_commands=[],
            source_cluster=cluster,
            confidence=0.3,
        )
        decisions = triage_skill_drafts([draft], discard_confidence=0.55)
        assert decisions[0].action == "discard"

    def test_new_when_no_existing(self, tmp_path):
        cluster = _make_cluster()
        draft = SkillDraft(
            kind="guard",
            name="guard-src-drift-signals",
            module_path="src/drift/signals",
            trigger="t",
            goal="g",
            trigger_signals=["PFS"],
            constraints=[],
            negative_examples=[],
            fix_patterns=[],
            verify_commands=[],
            source_cluster=cluster,
            confidence=0.8,
        )
        decisions = triage_skill_drafts([draft], repo_root=tmp_path)
        assert decisions[0].action == "new"

    def test_sprawl_guard(self, tmp_path):
        cluster = _make_cluster()
        draft = SkillDraft(
            kind="guard",
            name="guard-test",
            module_path="src/test",
            trigger="t",
            goal="g",
            trigger_signals=["PFS"],
            constraints=[],
            negative_examples=[],
            fix_patterns=[],
            verify_commands=[],
            source_cluster=cluster,
            confidence=0.8,
        )
        decisions = triage_skill_drafts([draft], repo_root=tmp_path, max_skills=0)
        assert decisions[0].action == "discard"
        assert decisions[0].sprawl_risk is True


# ===========================================================================
# Effectiveness Tracking
# ===========================================================================


class TestEffectivenessTracking:
    def test_save_and_load(self, tmp_path):
        rec = SkillEffectivenessRecord(
            skill_name="guard-test",
            created_at="2025-01-01T00:00:00+00:00",
            cluster_id="abc123",
            pre_recurrence_rate=0.8,
            post_recurrence_rate=None,
            scans_since_creation=0,
        )
        save_effectiveness_record(rec, tmp_path)
        loaded = load_effectiveness_records(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].skill_name == "guard-test"
        assert loaded[0].pre_recurrence_rate == 0.8

    def test_create_baseline(self, tmp_path):
        rec = create_effectiveness_baseline(
            "guard-test", "abc123", 0.8, tmp_path,
        )
        assert rec.post_recurrence_rate is None
        assert rec.scans_since_creation == 0
        loaded = load_effectiveness_records(tmp_path)
        assert len(loaded) == 1

    def test_update_effectiveness(self, tmp_path):
        baseline = create_effectiveness_baseline(
            "guard-test", "does_not_match", 0.8, tmp_path,
        )
        # No matching cluster → post_recurrence drops to 0.0
        finding = _make_finding()
        snapshots = [_make_snapshot([finding]) for _ in range(5)]
        updated = update_effectiveness([baseline], snapshots, tmp_path)
        assert len(updated) == 1
        assert updated[0].scans_since_creation == 1


# ===========================================================================
# Repair Skill Writer
# ===========================================================================


class TestRenderRepairSkillMd:
    def test_render_basic(self):
        from drift.synthesizer._skill_renderer import render_repair_skill_md

        draft_dict = {
            "kind": "repair",
            "name": "repair-pfs-src-drift-signals",
            "module_path": "src/drift/signals",
            "trigger": "Drift meldet PFS-Findings.",
            "goal": "PFS-Findings beheben.",
            "trigger_signals": ["PFS"],
            "constraints": ["[WARN] Keep functions small"],
            "negative_examples": ["Nicht anwenden bei generierten Dateien."],
            "fix_patterns": ["Docstrings ergaenzen."],
            "verify_commands": ["drift verify"],
            "confidence": 0.85,
        }
        text = render_repair_skill_md(draft_dict)
        assert "repair-pfs-src-drift-signals" in text
        assert "## Fix Patterns" in text
        assert "## Negative Examples" in text
        assert "## Verify" in text
        assert "drift synthesize" in text


# ===========================================================================
# API Layer
# ===========================================================================


class TestSynthesizeApi:
    def test_no_snapshots(self, tmp_path):
        pytest.importorskip(
            "drift.api.synthesize",
            reason="drift.api.synthesize not importable (pre-existing dep issue)",
        )
        from drift.api.synthesize import synthesize

        result = synthesize(repo=str(tmp_path))
        assert result["status"] == "insufficient_data"
        assert result["clusters"] == []

    def test_full_pipeline(self, tmp_path):
        pytest.importorskip(
            "drift.api.synthesize",
            reason="drift.api.synthesize not importable (pre-existing dep issue)",
        )
        from drift.api.synthesize import synthesize

        # Create history directory with snapshots
        history_dir = tmp_path / ".drift-cache" / "history"
        history_dir.mkdir(parents=True)

        finding = {
            "signal_type": "pattern_fragmentation",
            "file_path": "src/drift/signals/pfs.py",
            "score": 0.7,
            "start_line": 10,
        }
        for i in range(5):
            snapshot = {
                "timestamp": f"2025-01-0{i + 1}T00:00:00+00:00",
                "drift_score": 5.0,
                "finding_count": 1,
                "findings": [finding],
            }
            (history_dir / f"scan_{i}.json").write_text(
                json.dumps(snapshot), encoding="utf-8",
            )

        result = synthesize(
            repo=str(tmp_path),
            min_recurrence=3,
            min_recurrence_rate=0.5,
        )
        assert result["status"] in ("ok", "no_clusters")


# ===========================================================================
# CLI (Click)
# ===========================================================================


class TestSynthesizeCli:
    def test_command_exists(self):
        try:
            from drift.cli import main
        except ImportError:
            pytest.skip("drift.cli not importable (pre-existing dep issue)")
        cmds = {c for c in main.commands}
        assert "synthesize" in cmds

    def test_help_text(self):
        try:
            from drift.commands.synthesize_cmd import synthesize
        except ImportError:
            pytest.skip("synthesize_cmd not importable (pre-existing dep issue)")
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(synthesize, ["--help"])
        assert result.exit_code == 0
        assert "synthesize" in result.output.lower() or "skill" in result.output.lower()
