"""Tests for the SkillBriefing → SKILL.md text renderer.

Covers:
- render_skill_md() output format and content
- YAML frontmatter validity
- Section presence
- Signal-specific content
- Constraint rendering
- Edge cases: no constraints, no abstractions, no neighbors
"""

from __future__ import annotations

from drift.arch_graph._models import SkillBriefing

from drift.arch_graph._skill_writer import render_skill_md

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_briefing(**kwargs) -> SkillBriefing:
    defaults = dict(
        name="guard-src-api",
        module_path="src/api",
        trigger_signals=["EDS", "PFS"],
        constraints=[
            {"id": "adr-01", "rule": "No direct DB calls", "enforcement": "block"}
        ],
        hotspot_files=["src/api/routes.py", "src/api/handlers.py"],
        layer="api",
        neighbors=["src/core", "src/models"],
        abstractions=["BaseHandler", "validate_request"],
        confidence=0.85,
    )
    defaults.update(kwargs)
    return SkillBriefing(**defaults)


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_has_yaml_fences(self):
        md = render_skill_md(_make_briefing())
        assert md.startswith("---\n")
        second_fence = md.index("---\n", 4)
        assert second_fence > 0

    def test_frontmatter_contains_name(self):
        md = render_skill_md(_make_briefing())
        assert "name: guard-src-api" in md

    def test_frontmatter_description_contains_module_path(self):
        md = render_skill_md(_make_briefing())
        assert "src/api" in md

    def test_frontmatter_description_contains_signals(self):
        md = render_skill_md(_make_briefing())
        assert "EDS" in md
        assert "PFS" in md

    def test_frontmatter_description_contains_confidence(self):
        md = render_skill_md(_make_briefing())
        assert "0.85" in md

    def test_frontmatter_has_argument_hint(self):
        md = render_skill_md(_make_briefing())
        assert "argument-hint:" in md


# ---------------------------------------------------------------------------
# Required sections
# ---------------------------------------------------------------------------


class TestRequiredSections:
    def test_has_header(self):
        md = render_skill_md(_make_briefing())
        assert "# Guard: `src/api`" in md

    def test_has_when_to_use(self):
        md = render_skill_md(_make_briefing())
        assert "## When To Use" in md

    def test_has_core_rules(self):
        md = render_skill_md(_make_briefing())
        assert "## Core Rules" in md

    def test_has_review_checklist(self):
        md = render_skill_md(_make_briefing())
        assert "## Review Checklist" in md

    def test_has_references(self):
        md = render_skill_md(_make_briefing())
        assert "## References" in md

    def test_has_architecture_context(self):
        md = render_skill_md(_make_briefing())
        assert "## Architecture Context" in md


# ---------------------------------------------------------------------------
# Content: signals
# ---------------------------------------------------------------------------


class TestSignalContent:
    def test_when_to_use_mentions_each_signal(self):
        md = render_skill_md(_make_briefing(trigger_signals=["AVS", "EDS"]))
        assert "AVS" in md
        assert "EDS" in md

    def test_core_rules_covers_each_signal(self):
        md = render_skill_md(_make_briefing(trigger_signals=["PFS"]))
        assert "PFS" in md

    def test_checklist_has_signal_items(self):
        md = render_skill_md(_make_briefing(trigger_signals=["EDS"]))
        assert "EDS" in md

    def test_single_signal(self):
        md = render_skill_md(_make_briefing(trigger_signals=["AVS"]))
        assert "AVS" in md


# ---------------------------------------------------------------------------
# Content: constraints
# ---------------------------------------------------------------------------


class TestConstraintContent:
    def test_constraint_rule_appears_in_core_rules(self):
        md = render_skill_md(_make_briefing())
        assert "No direct DB calls" in md

    def test_constraint_enforcement_label_appears(self):
        md = render_skill_md(_make_briefing())
        # Enforcement is uppercased for readability in Markdown (e.g. BLOCK, WARN)
        assert "BLOCK" in md

    def test_no_constraints_still_renders(self):
        md = render_skill_md(_make_briefing(constraints=[]))
        assert "## Core Rules" in md

    def test_multiple_constraints_all_rendered(self):
        constraints = [
            {"id": "c1", "rule": "Rule Alpha", "enforcement": "warn"},
            {"id": "c2", "rule": "Rule Beta", "enforcement": "block"},
        ]
        md = render_skill_md(_make_briefing(constraints=constraints))
        assert "Rule Alpha" in md
        assert "Rule Beta" in md


# ---------------------------------------------------------------------------
# Content: architecture context
# ---------------------------------------------------------------------------


class TestArchitectureContext:
    def test_layer_appears(self):
        md = render_skill_md(_make_briefing(layer="api"))
        assert "api" in md

    def test_unknown_layer_fallback(self):
        md = render_skill_md(_make_briefing(layer=None))
        assert "unbekannt" in md

    def test_neighbors_listed(self):
        md = render_skill_md(_make_briefing(neighbors=["src/core", "src/models"]))
        assert "src/core" in md
        assert "src/models" in md

    def test_empty_neighbors(self):
        md = render_skill_md(_make_briefing(neighbors=[]))
        assert "## Architecture Context" in md

    def test_abstractions_listed(self):
        md = render_skill_md(_make_briefing(abstractions=["BaseHandler"]))
        assert "BaseHandler" in md

    def test_empty_abstractions(self):
        md = render_skill_md(_make_briefing(abstractions=[]))
        assert "## Architecture Context" in md


# ---------------------------------------------------------------------------
# Content: hotspot files in references
# ---------------------------------------------------------------------------


class TestHotspotReferences:
    def test_hotspot_files_in_references(self):
        md = render_skill_md(
            _make_briefing(hotspot_files=["src/api/routes.py"])
        )
        assert "routes.py" in md

    def test_no_hotspot_files(self):
        md = render_skill_md(_make_briefing(hotspot_files=[]))
        assert "## References" in md


# ---------------------------------------------------------------------------
# Checklist items
# ---------------------------------------------------------------------------


class TestChecklist:
    def test_checklist_has_nudge_item(self):
        md = render_skill_md(_make_briefing())
        assert "drift nudge" in md

    def test_checklist_items_use_checkbox_syntax(self):
        md = render_skill_md(_make_briefing())
        assert "- [ ]" in md

    def test_checklist_mentions_safe_to_commit(self):
        md = render_skill_md(_make_briefing())
        assert "safe_to_commit" in md
