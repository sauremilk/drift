"""Finding-context classification and triage helpers.

This module tags findings by operational context (production, fixture,
generated, migration, docs) using configurable glob rules plus lightweight
metadata heuristics.
"""

from __future__ import annotations

import fnmatch
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drift.config import DriftConfig
    from drift.models import Finding


def _normalise_context(raw: str | None, *, fallback: str = "production") -> str:
    if not raw:
        return fallback
    return raw.strip().lower() or fallback


def _ordered_rules(config: DriftConfig) -> list:
    rules = list(config.finding_context.rules)
    return sorted(
        rules,
        key=lambda r: (-int(r.precedence), -len(r.pattern), r.pattern),
    )


def _matches_rule(path_str: str, pattern: str) -> bool:
    norm_pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatch(path_str, norm_pattern):
        return True

    # Treat **/x/** as matching both nested and top-level x/...
    if norm_pattern.startswith("**/"):
        top_level_pattern = norm_pattern[3:]
        if fnmatch.fnmatch(path_str, top_level_pattern):
            return True

    if norm_pattern.startswith("**/") and norm_pattern.endswith("/**"):
        middle = norm_pattern[3:-3]
        for part in path_str.split("/"):
            if fnmatch.fnmatch(part, middle):
                return True
    return False


def classify_path_context(path: Path | None, config: DriftConfig) -> str:
    """Return context class for a file path using configured glob rules."""
    if path is None:
        return config.finding_context.default_context

    posix = path.as_posix()
    for rule in _ordered_rules(config):
        if _matches_rule(posix, rule.pattern):
            return _normalise_context(rule.context, fallback=config.finding_context.default_context)
    return config.finding_context.default_context


def classify_finding_context(finding: Finding, config: DriftConfig) -> str:
    """Classify a finding into an operational context."""
    existing = finding.metadata.get("finding_context")
    if isinstance(existing, str) and existing.strip():
        return _normalise_context(existing, fallback=config.finding_context.default_context)

    tags = finding.metadata.get("context_tags")
    if isinstance(tags, list):
        lowered = {_normalise_context(str(tag)) for tag in tags}
        if "fixture" in lowered:
            return "fixture"
        if "generated" in lowered:
            return "generated"
        if "migration" in lowered:
            return "migration"
        if "docs" in lowered:
            return "docs"

    generated_markers = (
        finding.metadata.get("generated") is True
        or finding.metadata.get("is_generated") is True
    )
    if generated_markers:
        return "generated"

    return classify_path_context(finding.file_path, config)


def annotate_finding_contexts(findings: list[Finding], config: DriftConfig) -> None:
    """Populate ``metadata.finding_context`` for all findings in place."""
    for finding in findings:
        finding.metadata["finding_context"] = classify_finding_context(finding, config)


def is_non_operational_context(context: str, config: DriftConfig) -> bool:
    """Return True when context belongs to the configured non-operational set."""
    non_operational = {
        _normalise_context(value)
        for value in config.finding_context.non_operational_contexts
    }
    return _normalise_context(context) in non_operational


def split_findings_by_context(
    findings: list[Finding],
    config: DriftConfig,
    *,
    include_non_operational: bool,
) -> tuple[list[Finding], list[Finding], dict[str, int]]:
    """Split findings into prioritized and excluded buckets by context."""
    prioritized: list[Finding] = []
    excluded: list[Finding] = []
    counts: Counter[str] = Counter()

    for finding in findings:
        context = classify_finding_context(finding, config)
        finding.metadata["finding_context"] = context
        counts[context] += 1
        if include_non_operational or not is_non_operational_context(context, config):
            prioritized.append(finding)
        else:
            excluded.append(finding)

    return prioritized, excluded, dict(sorted(counts.items()))