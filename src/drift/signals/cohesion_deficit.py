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


def _is_test_like(path: Path) -> bool:
    p = path.as_posix().lower()
    name = path.name.lower()
    return (
        "/tests/" in p
        or p.startswith("tests/")
        or name.startswith("test_")
        or name.endswith("_test.py")
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


@register_signal
class CohesionDeficitSignal(BaseSignal):
    """Detect semantically incoherent modules/files."""

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

        repo_python_files = [
            pr
            for pr in parse_results
            if pr.language == "python"
            and pr.file_path.suffix == ".py"
            and pr.file_path.name != "__init__.py"
            and not _is_test_like(pr.file_path)
        ]

        small_repo_threshold = config.thresholds.small_repo_module_threshold
        repo_ratio = min(1.0, len(repo_python_files) / max(1, small_repo_threshold))
        repo_dampening = 0.7 + (0.3 * repo_ratio)

        min_units = 4
        isolated_similarity_threshold = 0.15
        detection_threshold = 0.35

        findings: list[Finding] = []

        for pr in repo_python_files:
            units = _collect_units(pr)
            if len(units) < min_units:
                continue

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

            # Small member sets are noisier: ramp up confidence with module size.
            member_scale = min(1.0, (len(units) - 2) / 4)
            # Keep COD conservative for CI gating: severe but non-critical by default.
            score = round(min(0.79, raw_score * member_scale * repo_dampening), 3)

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
                        "member_scale": round(member_scale, 3),
                    },
                )
            )

        return findings
