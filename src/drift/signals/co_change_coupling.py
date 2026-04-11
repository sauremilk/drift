"""Signal: Co-Change Coupling (CCC).

Detects hidden coupling between files that repeatedly change together
without an explicit import relationship.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import is_test_file
from drift.models import (
    CommitInfo,
    FileHistory,
    Finding,
    ImportInfo,
    ParseResult,
    SignalType,
    severity_for_score,
)
from drift.signals.base import BaseSignal, register_signal

_MIN_HISTORY_COMMITS = 8
_MIN_EFFECTIVE_COMMITS = 4.0
_MIN_CO_CHANGE_WEIGHT = 2.5
_MIN_CONFIDENCE = 0.45
_MAX_FILES_PER_COMMIT = 20
_MAX_FINDINGS = 10

_MERGE_WEIGHT = 0.35
_AUTOMATED_WEIGHT = 0.50

_AUTOMATION_MARKERS = (
    "bot",
    "github-actions",
    "dependabot",
    "renovate",
    "release-please",
    "automation",
)


def _module_candidates(file_path: Path) -> set[str]:
    """Return plausible python module names for a file path."""
    normalized = file_path.as_posix().lstrip("./")
    if not normalized.endswith(".py"):
        return set()

    stem = normalized[:-3]
    candidates = {stem.replace("/", ".")}
    if stem.endswith("/__init__"):
        candidates.add(stem[: -len("/__init__")].replace("/", "."))
    return {c for c in candidates if c}


def _build_module_index(parse_results: list[ParseResult]) -> dict[str, set[str]]:
    """Map module names to candidate file paths in parse results."""
    index: dict[str, set[str]] = defaultdict(set)
    for pr in parse_results:
        for module in _module_candidates(pr.file_path):
            index[module].add(pr.file_path.as_posix())
    return index


def _resolve_non_relative_targets(imp: ImportInfo, module_index: dict[str, set[str]]) -> set[str]:
    """Resolve non-relative imports to known in-repo file paths."""
    targets: set[str] = set()
    module = imp.imported_module.lstrip(".")
    if not module:
        return targets

    if module in module_index:
        targets.update(module_index[module])

    for imported_name in imp.imported_names:
        nested = f"{module}.{imported_name}"
        if nested in module_index:
            targets.update(module_index[nested])

    return targets


def _resolve_relative_targets(source_file: Path, imp: ImportInfo) -> set[str]:
    """Resolve relative imports with conservative local path heuristics."""
    targets: set[str] = set()
    base = source_file.parent
    raw = imp.imported_module.strip()
    module_part = raw.lstrip(".")

    if module_part:
        rel = Path(module_part.replace(".", "/"))
        targets.add((base / f"{rel.as_posix()}.py").as_posix())
        targets.add((base / rel / "__init__.py").as_posix())

    for imported_name in imp.imported_names:
        rel_name = imported_name.replace(".", "/")
        targets.add((base / f"{rel_name}.py").as_posix())

    return targets


def _explicit_dependency_pairs(parse_results: list[ParseResult]) -> set[tuple[str, str]]:
    """Build undirected explicit dependency pairs from import metadata."""
    module_index = _build_module_index(parse_results)
    known_files = {pr.file_path.as_posix() for pr in parse_results}
    explicit: set[tuple[str, str]] = set()

    for pr in parse_results:
        source = pr.file_path.as_posix()
        for imp in pr.imports:
            if imp.is_relative:
                resolved = _resolve_relative_targets(pr.file_path, imp)
            else:
                resolved = _resolve_non_relative_targets(imp, module_index)

            for target in resolved:
                if target not in known_files or target == source:
                    continue
                pair = tuple(sorted((source, target)))
                explicit.add(pair)  # type: ignore[arg-type]

    return explicit


def _is_merge_commit(message: str) -> bool:
    """Heuristic merge commit detection from message text."""
    lower = message.lower().strip()
    return lower.startswith("merge ") or "merge pull request" in lower


def _is_automated_commit(commit: CommitInfo) -> bool:
    """Heuristic detection for bot/automated commits."""
    if commit.is_ai_attributed:
        return True

    haystack = " ".join(
        [
            commit.author.lower(),
            commit.email.lower(),
            commit.message.lower(),
        ]
    )
    return any(marker in haystack for marker in _AUTOMATION_MARKERS)


@register_signal
class CoChangeCouplingSignal(BaseSignal):
    """Detect hidden file coupling from recurring co-change patterns."""

    incremental_scope = "git_dependent"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.CO_CHANGE_COUPLING

    @property
    def name(self) -> str:
        return "Co-Change Coupling"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        """Find repeated co-change pairs without explicit import edges.

        Uses only commit metadata from AnalysisContext, with deterministic
        weighting to avoid over-emphasizing merge and automated commits.
        """
        del file_histories
        handling = config.test_file_handling or "reduce_severity"

        if len(self.commits) < _MIN_HISTORY_COMMITS:
            return []

        known_files = {pr.file_path.as_posix() for pr in parse_results}
        if len(known_files) < 2:
            return []

        explicit_pairs = _explicit_dependency_pairs(parse_results)

        file_weights: dict[str, float] = defaultdict(float)
        pair_weights: dict[tuple[str, str], float] = defaultdict(float)
        pair_raw_counts: dict[tuple[str, str], int] = defaultdict(int)
        pair_commit_hashes: dict[tuple[str, str], list[str]] = defaultdict(list)
        pair_commit_messages: dict[tuple[str, str], list[str]] = defaultdict(list)

        effective_commits = 0.0

        for commit in self.commits:
            files = sorted({f for f in commit.files_changed if f in known_files})
            if len(files) < 2 or len(files) > _MAX_FILES_PER_COMMIT:
                continue

            weight = 1.0
            if _is_merge_commit(commit.message):
                weight *= _MERGE_WEIGHT
            if _is_automated_commit(commit):
                weight *= _AUTOMATED_WEIGHT

            if weight <= 0.0:
                continue

            effective_commits += weight
            for file_path in files:
                file_weights[file_path] += weight

            for file_a, file_b in combinations(files, 2):
                pair = (file_a, file_b)
                pair_weights[pair] += weight
                pair_raw_counts[pair] += 1
                pair_commit_hashes[pair].append(commit.hash)
                pair_commit_messages[pair].append(commit.message[:60])

        if effective_commits < _MIN_EFFECTIVE_COMMITS:
            return []

        findings: list[Finding] = []
        for pair, weighted_count in pair_weights.items():
            if weighted_count < _MIN_CO_CHANGE_WEIGHT:
                continue
            if pair in explicit_pairs:
                continue

            total_a = file_weights[pair[0]]
            total_b = file_weights[pair[1]]
            denom = min(total_a, total_b)
            if denom <= 0.0:
                continue

            confidence = weighted_count / denom
            if confidence < _MIN_CONFIDENCE:
                continue

            support = min(1.0, weighted_count / 8.0)
            raw_score = max(0.0, (0.55 * confidence) + (0.45 * support))
            # Keep initial rollout conservative: hidden co-change findings
            # should not auto-escalate to CRITICAL without explicit validation.
            score = min(0.79, raw_score)
            if score < 0.2:
                continue

            path_a = Path(str(pair[0]))
            path_b = Path(str(pair[1]))
            pair_has_test = is_test_file(path_a) or is_test_file(path_b)
            if pair_has_test and handling == "exclude":
                continue

            if pair_has_test and handling == "reduce_severity":
                score = round(score * 0.5, 3)
                if score < 0.2:
                    continue

            sample_hashes = sorted(set(pair_commit_hashes[pair]))[:5]
            raw_count = pair_raw_counts[pair]
            sample_messages = pair_commit_messages[pair][:3]
            msg_context = (
                "\n".join(f'  - "{m}"' for m in sample_messages)
                if sample_messages
                else ""
            )

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity_for_score(score),
                    score=round(score, 3),
                    title=(
                        f"Hidden co-change coupling: {path_a.name} <-> {path_b.name} "
                        f"({raw_count} commits)"
                    ),
                    description=(
                        f"{pair[0]} and {pair[1]} changed together repeatedly "  # type: ignore[index]
                        f"(weighted={weighted_count:.2f}, confidence={confidence:.0%}) "
                        f"without an explicit import relationship. "
                        "This indicates hidden coupling and implicit change propagation risk."
                    ),
                    file_path=path_a,
                    related_files=[path_b],
                    fix=(
                        f"Co-change coupling: {path_a.name} \u2194 {path_b.name}."
                        + (f"\nRecent context:\n{msg_context}" if msg_context else "")
                        + "\n\nIf intentional (shared boundary):\n"
                        + "  \u2192 Add integration test: "
                        + f"def test_{path_a.stem}_{path_b.stem}_sync():\n"
                        + "        # Verify consistent contracts between both modules\n"
                        + "\nIf accidental (layering issue):\n"
                        + "  \u2192 Extract shared logic into src/<domain>/shared.py"
                    ),
                    metadata={
                        "file_a": pair[0],
                        "file_b": pair[1],
                        "co_change_commits": raw_count,
                        "co_change_weight": round(weighted_count, 3),
                        "confidence": round(confidence, 3),
                        "total_weight_file_a": round(total_a, 3),
                        "total_weight_file_b": round(total_b, 3),
                        "explicit_dependency": False,
                        "commit_samples": sample_hashes,
                        "commit_messages": sample_messages,
                        "finding_context": "test" if pair_has_test else "production",
                    },
                    finding_context="test" if pair_has_test else "production",
                )
            )

        findings.sort(  # type: ignore[union-attr]
            key=lambda f: (-f.score, f.file_path.as_posix() if f.file_path else "", f.title)
        )
        return findings[:_MAX_FINDINGS]
