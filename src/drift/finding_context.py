"""Finding-context classification and triage helpers.

This module tags findings by operational context (production, fixture,
generated, migration, docs) using configurable glob rules plus lightweight
metadata heuristics.
"""

from __future__ import annotations

import fnmatch
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from drift.ingestion.test_detection import classify_file_context

if TYPE_CHECKING:
    from drift.config import DriftConfig
    from drift.models import Finding


_LIBRARY_CONTEXT_SIGNALS: frozenset[str] = frozenset({
    "dead_code_accumulation",
    "doc_impl_drift",
    "naming_contract_violation",
})

_VENDORED_DIR_MARKERS: frozenset[str] = frozenset({
    "vendor",
    "vendors",
    "vendored",
    "third_party",
    "third-party",
    "thirdparty",
    "external",
})

_VENDORED_HEADER_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\badapted from\b"),
    re.compile(r"\bported from\b"),
    re.compile(r"\bvendored\b"),
    re.compile(r"\bvendor(?:ed|ized)? from\b"),
)
_VENDORED_HEADER_MAX_LINES = 80


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

    baseline_context = classify_file_context(path)
    if baseline_context == "test":
        return baseline_context

    posix = path.as_posix()
    for rule in _ordered_rules(config):
        if _matches_rule(posix, rule.pattern):
            return _normalise_context(rule.context, fallback=config.finding_context.default_context)
    return config.finding_context.default_context


def _ensure_metadata_dict(finding: Finding) -> dict[str, object]:
    """Return mutable metadata dict for finding-like objects.

    Some API/test paths pass lightweight finding-like objects (e.g. SimpleNamespace)
    without a ``metadata`` attribute. Normalize those to an empty dict so context
    classification remains robust.
    """
    meta = getattr(finding, "metadata", None)
    if isinstance(meta, dict):
        return meta
    new_meta: dict[str, object] = {}
    try:
        finding.metadata = new_meta
    except Exception:
        # Fallback for objects that disallow attribute writes.
        return new_meta
    return new_meta


def _path_contains_vendored_marker(path: Path) -> bool:
    return any(part.lower() in _VENDORED_DIR_MARKERS for part in path.parts)


@lru_cache(maxsize=8192)
def _file_header_contains_vendored_marker(path_str: str) -> bool:
    path = Path(path_str)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            header = "\n".join(
                line.strip().lower()
                for _, line in zip(range(_VENDORED_HEADER_MAX_LINES), handle, strict=False)
            )
    except OSError:
        return False
    return any(pattern.search(header) for pattern in _VENDORED_HEADER_MARKERS)


def _is_vendored_or_adapted_file(path: Path | PurePath | None) -> bool:
    if path is None:
        return False

    concrete_path = Path(str(path))

    if _path_contains_vendored_marker(concrete_path):
        return True

    if _file_header_contains_vendored_marker(concrete_path.as_posix()):
        return True

    # Fall back to absolute path resolution for relative file paths.
    if not concrete_path.is_absolute():
        return _file_header_contains_vendored_marker(str(concrete_path.resolve()))

    return False


def classify_finding_context(finding: Finding, config: DriftConfig) -> str:
    """Classify a finding into an operational context."""
    metadata = _ensure_metadata_dict(finding)

    existing = metadata.get("finding_context")
    if isinstance(existing, str) and existing.strip():
        return _normalise_context(existing, fallback=config.finding_context.default_context)

    tags = metadata.get("context_tags")
    if isinstance(tags, list):
        lowered = {_normalise_context(str(tag)) for tag in tags}
        if "library" in lowered:
            return "library"
        if "fixture" in lowered:
            return "fixture"
        if "generated" in lowered:
            return "generated"
        if "migration" in lowered:
            return "migration"
        if "docs" in lowered:
            return "docs"

    if _is_vendored_or_adapted_file(finding.file_path):
        metadata["vendored_context_candidate"] = True
        return "library"

    signal_type = str(getattr(finding, "signal_type", "")).strip().lower()
    if (
        signal_type in _LIBRARY_CONTEXT_SIGNALS
        and metadata.get("library_context_candidate") is True
    ):
        return "library"

    generated_markers = metadata.get("generated") is True or metadata.get("is_generated") is True
    if generated_markers:
        return "generated"

    return classify_path_context(finding.file_path, config)


def annotate_finding_contexts(findings: list[Finding], config: DriftConfig) -> None:
    """Populate ``metadata.finding_context`` for all findings in place."""
    for finding in findings:
        metadata = _ensure_metadata_dict(finding)
        metadata["finding_context"] = classify_finding_context(finding, config)


def is_non_operational_context(context: str, config: DriftConfig) -> bool:
    """Return True when context belongs to the configured non-operational set."""
    non_operational = {
        _normalise_context(value)
        for value in config.finding_context.non_operational_contexts
    }
    return _normalise_context(context) in non_operational


def _is_actionable_docs_finding(finding: Finding, context: str) -> bool:
    """Return True for docs-context findings that still need agent attention."""
    signal_type = str(getattr(finding, "signal_type", "")).strip().lower()
    return context == "docs" and signal_type == "doc_impl_drift"


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
        metadata = _ensure_metadata_dict(finding)
        metadata["finding_context"] = context
        counts[context] += 1
        if (
            include_non_operational
            or not is_non_operational_context(context, config)
            or _is_actionable_docs_finding(finding, context)
        ):
            prioritized.append(finding)
        else:
            excluded.append(finding)

    return prioritized, excluded, dict(sorted(counts.items()))
