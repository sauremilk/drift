"""Signal 4: Explainability Deficit Score (EDS).

Detects functions with high complexity but insufficient documentation,
test coverage indicators, or commit rationale — especially when
AI-attributed, indicating "accepted without understanding."
"""

from __future__ import annotations

from typing import Any

from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal

# Defaults (overridden by config.thresholds)
HIGH_COMPLEXITY = 10
MEDIUM_COMPLEXITY = 5


def _explanation_score(func: FunctionInfo, has_test: bool) -> float:
    """Calculate how well-explained a function is (0.0=unexplained, 1.0=well-explained)."""
    evidence = 0.0
    max_evidence = 4.0

    if func.has_docstring:
        evidence += 1.0

    if has_test:
        evidence += 1.5

    # Decorators suggest framework integration (router, property, etc.)
    if func.decorators:
        evidence += 0.5

    # Return type annotation suggests intentional design
    if func.return_type:
        evidence += 1.0

    return min(1.0, evidence / max_evidence)


class ExplainabilityDeficitSignal(BaseSignal):
    """Detect complex functions lacking documentation and tests."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.EXPLAINABILITY_DEFICIT

    @property
    def name(self) -> str:
        return "Explainability Deficit"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: Any,
    ) -> list[Finding]:
        # Collect all function names for test detection
        all_functions: dict[str, FunctionInfo] = {}
        test_targets: set[str] = set()

        for pr in parse_results:
            for fn in pr.functions:
                all_functions[f"{fn.file_path}:{fn.name}"] = fn

                # Heuristic: functions in test files suggest tests for other functions
                if "test" in fn.file_path.as_posix().lower():
                    # test_foo → foo, test_handle_payment → handle_payment
                    target_name = fn.name.removeprefix("test_")
                    test_targets.add(target_name)
                    # Also handle class.method style
                    if "." in fn.name:
                        _, method = fn.name.rsplit(".", 1)
                        test_targets.add(method.removeprefix("test_"))

        # Resolve thresholds from config
        medium_complexity = MEDIUM_COMPLEXITY
        min_func_loc = 10
        if hasattr(config, "thresholds"):
            medium_complexity = config.thresholds.medium_complexity
            min_func_loc = config.thresholds.min_function_loc

        findings: list[Finding] = []

        for key, func in all_functions.items():
            # Skip test files and trivial functions
            if "test" in func.file_path.as_posix().lower():
                continue
            if func.complexity < medium_complexity:
                continue
            if func.loc < min_func_loc:
                continue

            # Check if there's a corresponding test
            base_name = func.name.split(".")[-1] if "." in func.name else func.name
            has_test = base_name in test_targets

            explanation = _explanation_score(func, has_test)
            deficit = 1.0 - explanation

            # Weight by complexity
            complexity_factor = min(1.0, func.complexity / 20)
            weighted_score = deficit * complexity_factor

            if weighted_score < 0.3:
                continue

            # Check AI attribution for the file
            fpath_str = func.file_path.as_posix()
            history = file_histories.get(fpath_str)
            ai_related = history.ai_attributed_commits > 0 if history else False

            severity = Severity.INFO
            if weighted_score >= 0.7:
                severity = Severity.HIGH
            elif weighted_score >= 0.5:
                severity = Severity.MEDIUM
            elif weighted_score >= 0.3:
                severity = Severity.LOW

            desc_parts = [
                f"Complexity: {func.complexity}, LOC: {func.loc}.",
            ]
            if not func.has_docstring:
                desc_parts.append("No docstring.")
            if not has_test:
                desc_parts.append("No corresponding test found.")
            if not func.return_type:
                desc_parts.append("No return type annotation.")
            if ai_related:
                desc_parts.append("File contains AI-attributed commits.")

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=round(weighted_score, 3),
                    title=f"Unexplained complexity: {func.name}",
                    description=" ".join(desc_parts),
                    file_path=func.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    ai_attributed=ai_related,
                    metadata={
                        "complexity": func.complexity,
                        "loc": func.loc,
                        "has_docstring": func.has_docstring,
                        "has_test": has_test,
                        "has_return_type": func.return_type is not None,
                        "explanation_score": round(explanation, 3),
                    },
                )
            )

        return findings
