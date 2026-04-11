"""Signal: Cohesion Deficit (COD).

Detects files that contain many semantically unrelated responsibilities,
for example "god modules" or dump-like utility files.

The detector is deterministic and LLM-free:
- build semantic token sets from function/class names
- measure pairwise name-overlap (Jaccard similarity)
- flag files where most units do not cohere with each other
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    ClassInfo,
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    SignalType,
    severity_for_score,
)
from drift.signals._utils import _SUPPORTED_LANGUAGES
from drift.signals.base import BaseSignal, register_signal

_CAMEL_PART_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+")
_TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")

_STOPWORDS: frozenset[str] = frozenset(
    {
        "get",
        "set",
        "run",
        "make",
        "create",
        "build",
        "helper",
        "utils",
        "util",
        "common",
        "module",
        "data",
        "item",
        "value",
        "manager",
        "service",
        "handler",
        "process",
        "core",
        "base",
        "main",
        "file",
        "object",
    }
)


@dataclass(frozen=True)
class _SemanticUnit:
    name: str
    start_line: int
    end_line: int
    tokens: frozenset[str]


_INDEX_NAMES: frozenset[str] = frozenset(
    {"__init__.py", "index.ts", "index.tsx", "index.js", "index.jsx"},
)

_LOGGER_LEVEL_NAMES: frozenset[str] = frozenset(
    {"trace", "debug", "info", "warn", "warning", "error", "fatal", "log"}
)

_UTILITY_FILENAME_HINTS: frozenset[str] = frozenset(
    {"util", "utils", "helper", "helpers", "constant", "constants"}
)

_COHESIVE_ACTION_PREFIXES: frozenset[str] = frozenset(
    {"register", "format", "create"}
)


def _is_test_like(path: Path) -> bool:
    p = path.as_posix().lower()
    name = path.name.lower()
    return (
        "/tests/" in p
        or p.startswith("tests/")
        or "/__tests__/" in p
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".test.js")
        or name.endswith(".test.jsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
        or name.endswith(".spec.js")
        or name.endswith(".spec.jsx")
    )


def _tokenize_name(name: str) -> set[str]:
    base = name.split(".")[-1]
    chunks = _TOKEN_SPLIT_RE.split(base)
    tokens: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        parts = _CAMEL_PART_RE.findall(chunk) or [chunk]
        for part in parts:
            token = part.lower()
            if len(token) < 3:
                continue
            if token in _STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    inter = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return inter / union


def _function_unit(fn: FunctionInfo) -> _SemanticUnit | None:
    if "." in fn.name:
        return None
    tokens = _tokenize_name(fn.name)
    if len(tokens) < 1:
        return None
    return _SemanticUnit(
        name=fn.name,
        start_line=fn.start_line,
        end_line=fn.end_line,
        tokens=frozenset(tokens),
    )


def _class_unit(cls: ClassInfo) -> _SemanticUnit | None:
    tokens = _tokenize_name(cls.name)
    for method in cls.methods:
        tokens.update(_tokenize_name(method.name))
    if len(tokens) < 1:
        return None
    return _SemanticUnit(
        name=cls.name,
        start_line=cls.start_line,
        end_line=cls.end_line,
        tokens=frozenset(tokens),
    )


def _collect_units(parse_result: ParseResult) -> list[_SemanticUnit]:
    units: list[_SemanticUnit] = []
    for fn in parse_result.functions:
        unit = _function_unit(fn)
        if unit:
            units.append(unit)
    for cls in parse_result.classes:
        unit = _class_unit(cls)
        if unit:
            units.append(unit)
    return units


def _name_tokens(name: str) -> set[str]:
    return _tokenize_name(name)


def _is_logger_like_module(parse_result: ParseResult, units: list[_SemanticUnit]) -> bool:
    stem_tokens = _name_tokens(parse_result.file_path.stem)
    if "logger" in stem_tokens:
        return True

    scored_names = [u.name.split(".")[-1].lower() for u in units]
    if not scored_names:
        return False

    logger_like_count = 0
    for name in scored_names:
        tokens = _name_tokens(name)
        if tokens & _LOGGER_LEVEL_NAMES:
            logger_like_count += 1
            continue
        if "logger" in tokens or name.startswith("log"):
            logger_like_count += 1

    return (logger_like_count / len(scored_names)) >= 0.5


def _has_utility_filename_hint(path: Path) -> bool:
    stem = path.stem.lower()
    split_tokens = [part for part in _TOKEN_SPLIT_RE.split(stem) if part]
    for token in split_tokens:
        if token in _UTILITY_FILENAME_HINTS:
            return True
    return any(hint in stem for hint in _UTILITY_FILENAME_HINTS)


def _leading_token(name: str) -> str:
    tokens = _CAMEL_PART_RE.findall(name.split(".")[-1])
    if not tokens:
        return ""
    return tokens[0].lower()


def _shared_action_prefix_ratio(units: list[_SemanticUnit]) -> float:
    if not units:
        return 0.0

    prefix_count: dict[str, int] = {}
    for unit in units:
        prefix = _leading_token(unit.name)
        if prefix not in _COHESIVE_ACTION_PREFIXES:
            continue
        prefix_count[prefix] = prefix_count.get(prefix, 0) + 1

    if not prefix_count:
        return 0.0
    return max(prefix_count.values()) / len(units)


def _filename_token_cohesion_ratio(path: Path, units: list[_SemanticUnit]) -> float:
    stem_tokens = _name_tokens(path.stem)
    if not stem_tokens or not units:
        return 0.0

    covered = sum(1 for unit in units if unit.tokens & stem_tokens)
    return covered / len(units)


def _is_plugin_workspace_source(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    if len(parts) < 3:
        return False
    return parts[0] == "extensions" and "src" in parts[2:]


@register_signal
class CohesionDeficitSignal(BaseSignal):
    """Detect semantically incoherent modules/files."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.COHESION_DEFICIT

    @property
    def name(self) -> str:
        return "Cohesion Deficit"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        del file_histories  # Not required for this structural signal.

        repo_files = [
            pr
            for pr in parse_results
            if pr.language in _SUPPORTED_LANGUAGES
            and pr.file_path.name not in _INDEX_NAMES
            and not _is_test_like(pr.file_path)
        ]

        small_repo_threshold = config.thresholds.small_repo_module_threshold
        repo_ratio = min(1.0, len(repo_files) / max(1, small_repo_threshold))
        repo_dampening = 0.7 + (0.3 * repo_ratio)

        min_units = 4
        isolated_similarity_threshold = 0.15
        detection_threshold = 0.35

        findings: list[Finding] = []

        for pr in repo_files:
            units = _collect_units(pr)
            if len(units) < min_units:
                continue

            is_logger_like = _is_logger_like_module(pr, units)
            has_utility_filename_hint = _has_utility_filename_hint(pr.file_path)
            shared_action_prefix_ratio = _shared_action_prefix_ratio(units)
            filename_token_cohesion_ratio = _filename_token_cohesion_ratio(
                pr.file_path, units
            )
            is_plugin_workspace_source = _is_plugin_workspace_source(pr.file_path)

            best_similarities: list[float] = []
            isolated_names: list[str] = []

            for idx, unit in enumerate(units):
                best = 0.0
                for jdx, other in enumerate(units):
                    if idx == jdx:
                        continue
                    best = max(best, _jaccard(unit.tokens, other.tokens))
                best_similarities.append(best)
                if best < isolated_similarity_threshold:
                    isolated_names.append(unit.name)

            mean_best_similarity = sum(best_similarities) / len(best_similarities)
            isolation_ratio = len(isolated_names) / len(units)
            diversity = 1.0 - mean_best_similarity

            # 65% isolation, 35% global incoherence.
            raw_score = (0.65 * isolation_ratio) + (0.35 * diversity)

            module_pattern_dampening = 1.0
            if is_logger_like:
                # Logger facades intentionally expose independent severity entrypoints.
                module_pattern_dampening *= 0.35
            if has_utility_filename_hint and not is_logger_like:
                # Utility modules can contain loosely related helpers by convention.
                module_pattern_dampening *= 0.8
            if shared_action_prefix_ratio >= 0.6:
                # Action families like register*/format*/create* can still be cohesive.
                module_pattern_dampening *= 0.55
            if filename_token_cohesion_ratio >= 0.5:
                # format.ts/serializer.ts-like modules often reflect a single domain concern.
                module_pattern_dampening *= 0.7
            if (
                is_plugin_workspace_source
                and (shared_action_prefix_ratio >= 0.6 or filename_token_cohesion_ratio >= 0.5)
                and not is_logger_like
            ):
                # Extension workspaces frequently group one plugin concern per module.
                module_pattern_dampening *= 0.8

            # Small member sets are noisier: ramp up confidence with module size.
            member_scale = min(1.0, (len(units) - 2) / 4)
            # Keep COD conservative for CI gating: severe but non-critical by default.
            score = round(
                min(
                    0.79,
                    raw_score
                    * member_scale
                    * repo_dampening
                    * module_pattern_dampening,
                ),
                3,
            )

            if score < detection_threshold:
                continue

            severity = severity_for_score(score)
            file_path = pr.file_path
            isolated_preview = ", ".join(isolated_names[:5])
            if len(isolated_names) > 5:
                isolated_preview += f" (+{len(isolated_names) - 5} more)"

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=f"Cohesion deficit in {file_path.as_posix()}",
                    description=(
                        f"{len(isolated_names)}/{len(units)} semantic units are isolated "
                        f"(mean best similarity={mean_best_similarity:.2f}, "
                        f"isolation ratio={isolation_ratio:.2f})."
                    ),
                    file_path=file_path,
                    related_files=[file_path],
                    fix=(
                        f"Split {len(isolated_names)} isolated units into focused modules. "
                        f"Start with: {isolated_preview}. "
                        f"Move each cohesive group into its own module."
                    ),
                    metadata={
                        "unit_count": len(units),
                        "isolated_count": len(isolated_names),
                        "isolated_units": isolated_names,
                        "mean_best_similarity": round(mean_best_similarity, 3),
                        "isolation_ratio": round(isolation_ratio, 3),
                        "repo_dampening": round(repo_dampening, 3),
                        "module_pattern_dampening": round(module_pattern_dampening, 3),
                        "logger_like_module": is_logger_like,
                        "utility_filename_hint": has_utility_filename_hint,
                        "shared_action_prefix_ratio": round(
                            shared_action_prefix_ratio, 3
                        ),
                        "filename_token_cohesion_ratio": round(
                            filename_token_cohesion_ratio, 3
                        ),
                        "plugin_workspace_source": is_plugin_workspace_source,
                        "member_scale": round(member_scale, 3),
                    },
                )
            )

        return findings
