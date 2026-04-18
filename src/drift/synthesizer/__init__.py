"""Skill Synthesizer — closed-loop skill generation from recurring findings.

This package clusters recurring drift findings, generates guard and repair
skill drafts, triages them against existing skills, and tracks effectiveness.

Public API::

    from drift.synthesizer import (
        FindingCluster,
        SkillDraft,
        TriageDecision,
        build_finding_clusters,
        generate_skill_drafts,
        triage_skill_drafts,
        render_repair_skill_md,
    )
"""

from __future__ import annotations

from drift.synthesizer._cluster import build_finding_clusters
from drift.synthesizer._draft_generator import generate_skill_drafts
from drift.synthesizer._models import (
    ClusterFeedback,
    FindingCluster,
    SkillDraft,
    SkillEffectivenessRecord,
    TriageDecision,
)
from drift.synthesizer._skill_renderer import render_repair_skill_md
from drift.synthesizer._triage import triage_skill_drafts

__all__ = [
    "ClusterFeedback",
    "FindingCluster",
    "SkillDraft",
    "SkillEffectivenessRecord",
    "TriageDecision",
    "build_finding_clusters",
    "generate_skill_drafts",
    "render_repair_skill_md",
    "triage_skill_drafts",
]
