"""Triage engine — decide new / merge / discard for each skill draft."""

from __future__ import annotations

import re
from pathlib import Path

from drift.synthesizer._models import SkillDraft, TriageDecision


def _list_existing_skills(repo_root: Path) -> dict[str, list[str]]:
    """Scan .github/skills/*/SKILL.md for existing skill names and trigger signals.

    Returns mapping of skill_name → trigger_signals found in frontmatter or body.
    """
    skills_dir = repo_root / ".github" / "skills"
    if not skills_dir.is_dir():
        return {}

    result: dict[str, list[str]] = {}
    signal_pattern = re.compile(r"\b(AVS|EDS|MDS|PFS|CCC|DIA|BEM|GCD|BAT|NBV|PHR)\b")
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue
        signals = signal_pattern.findall(content)
        result[skill_dir.name] = sorted(set(signals))

    return result


def _compute_overlap(
    draft_signals: list[str],
    draft_module: str,
    existing_name: str,
    existing_signals: list[str],
) -> float:
    """Estimate overlap between a draft and an existing skill.

    1.0 = perfect match, 0.0 = no relation.
    """
    score = 0.0

    # Signal overlap
    common = set(draft_signals) & set(existing_signals)
    if existing_signals and common:
        score += 0.5 * len(common) / len(set(draft_signals) | set(existing_signals))

    # Name/module overlap
    normalised_name = existing_name.replace("-", "/").replace("_", "/").lower()
    normalised_module = draft_module.replace("\\", "/").lower()
    if normalised_module and normalised_module in normalised_name:
        score += 0.5
    elif normalised_name in normalised_module:
        score += 0.3

    return min(score, 1.0)


def triage_skill_drafts(
    drafts: list[SkillDraft],
    *,
    repo_root: Path | None = None,
    max_skills: int = 25,
    merge_threshold: float = 0.4,
    discard_confidence: float = 0.55,
) -> list[TriageDecision]:
    """Triage each draft: new skill, merge into existing, or discard.

    Parameters
    ----------
    drafts:
        Skill drafts from ``generate_skill_drafts()``.
    repo_root:
        Repository root for scanning existing skills.
    max_skills:
        Maximum total skills to prevent sprawl.
    merge_threshold:
        Overlap score above which → merge recommendation.
    discard_confidence:
        Drafts below this confidence → discard.

    Returns
    -------
    list[TriageDecision]
        One decision per draft, sorted by action priority (new > merge > discard).
    """
    existing = _list_existing_skills(repo_root) if repo_root else {}
    total_existing = len(existing)

    decisions: list[TriageDecision] = []
    proposed_new = 0

    for draft in drafts:
        decision = _triage_single(
            draft,
            existing,
            total_existing + proposed_new,
            max_skills=max_skills,
            merge_threshold=merge_threshold,
            discard_confidence=discard_confidence,
        )
        if decision.action == "new":
            proposed_new += 1
        decisions.append(decision)

    # Sort: new first, merge second, discard last
    action_order: dict[str, int] = {"new": 0, "merge": 1, "discard": 2}
    decisions.sort(key=lambda d: (action_order.get(d.action, 3), -d.draft.confidence))
    return decisions


def _triage_single(
    draft: SkillDraft,
    existing: dict[str, list[str]],
    current_count: int,
    *,
    max_skills: int,
    merge_threshold: float,
    discard_confidence: float,
) -> TriageDecision:
    """Decide the action for a single draft."""
    # Low confidence → discard
    if draft.confidence < discard_confidence:
        return TriageDecision(
            draft=draft,
            action="discard",
            merge_target=None,
            reason=f"Konfidenz {draft.confidence:.2f} unter Schwelle {discard_confidence}.",
            sprawl_risk=False,
        )

    # Check overlap with existing skills
    best_overlap = 0.0
    best_match = ""
    for name, signals in existing.items():
        overlap = _compute_overlap(draft.trigger_signals, draft.module_path, name, signals)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = name

    # High overlap → merge
    if best_overlap >= merge_threshold:
        return TriageDecision(
            draft=draft,
            action="merge",
            merge_target=best_match,
            reason=f"Ueberlappung {best_overlap:.0%} mit bestehendem Skill '{best_match}'.",
            sprawl_risk=False,
        )

    # Sprawl check
    sprawl = current_count >= max_skills
    if sprawl:
        return TriageDecision(
            draft=draft,
            action="discard",
            merge_target=None,
            reason=f"Sprawl-Guard: {current_count} Skills erreicht (max {max_skills}).",
            sprawl_risk=True,
        )

    # New skill
    return TriageDecision(
        draft=draft,
        action="new",
        merge_target=None,
        reason="Kein bestehender Skill deckt diesen Befund-Cluster ab.",
        sprawl_risk=False,
    )
