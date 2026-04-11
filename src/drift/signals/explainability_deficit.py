"""Signal 4: Explainability Deficit Score (EDS).

Detects functions with high complexity but insufficient documentation,
test coverage indicators, or commit rationale — especially when
AI-attributed, indicating "accepted without understanding."
"""

from __future__ import annotations

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

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


@register_signal
class ExplainabilityDeficitSignal(BaseSignal):
    """Detect complex functions lacking documentation and tests."""

    incremental_scope = "file_local"

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
        config: DriftConfig,
    ) -> list[Finding]:
        """Flag functions with high cyclomatic complexity but no docstring.

        Thresholds from config: min_function_loc and min_complexity.
        Test files and functions whose name appears as a test target are excluded.
        """
        all_functions: dict[str, FunctionInfo] = {}
        test_targets: set[str] = set()

        for pr in parse_results:
            for fn in pr.functions:
                all_functions[f"{fn.file_path}:{fn.name}"] = fn

                file_posix = fn.file_path.as_posix().lower()
                is_test_file = (
                    "test" in file_posix
                    or file_posix.endswith(".spec.ts")
                    or file_posix.endswith(".spec.tsx")
                )

                # Heuristic: functions in test files suggest tests for other functions
                if is_test_file:
                    # Python: test_foo → foo, test_handle_payment → handle_payment
                    target_name = fn.name.removeprefix("test_")
                    test_targets.add(target_name)
                    # Also handle class.method style
                    if "." in fn.name:
                        _, method = fn.name.rsplit(".", 1)
                        test_targets.add(method.removeprefix("test_"))

                    # Decorator-aware: pytest.mark.parametrize hints at
                    # thorough testing of the target function
                    for dec in fn.decorators:
                        if "parametrize" in dec or "fixture" in dec:
                            test_targets.add(target_name)
                            break

                    # setUp/tearDown style (unittest)
                    if fn.name in ("setUp", "tearDown", "setUpClass"):
                        # Mark all functions in the same file as tested
                        for other in pr.functions:
                            if not other.name.startswith("test_"):
                                test_targets.add(other.name)

                # TS/JS test patterns: describe("Foo", ...), it("should ...", ...)
                # Functions named it/test/describe inside test files hint at testing
                if (
                    fn.language in ("typescript", "tsx", "javascript", "jsx")
                    and is_test_file
                    and fn.name
                    not in (
                        "describe",
                        "it",
                        "test",
                        "beforeEach",
                        "afterEach",
                        "beforeAll",
                        "afterAll",
                    )
                ):
                    # All non-test-framework functions in spec files
                    # mark the subjects they exercise as "tested"
                    test_targets.add(fn.name)

        # Resolve thresholds from config
        min_complexity = MEDIUM_COMPLEXITY
        min_func_loc = 10
        if hasattr(config, "thresholds"):
            min_complexity = config.thresholds.min_complexity
            min_func_loc = config.thresholds.min_function_loc

        findings: list[Finding] = []

        for _key, func in all_functions.items():
            # Skip test files and trivial functions
            file_posix = func.file_path.as_posix().lower()
            if (
                "test" in file_posix
                or file_posix.endswith(".spec.ts")
                or file_posix.endswith(".spec.tsx")
            ):
                continue
            # Primary gate: cyclomatic complexity (better proxy for
            # "needs explanation" than raw LOC)
            if func.complexity < min_complexity:
                continue
            # Secondary gate: skip very short functions even if complex
            if func.loc < min_func_loc:
                continue

            # Skip __init__ methods – the class docstring covers their intent
            base_name = func.name.split(".")[-1] if "." in func.name else func.name
            if base_name == "__init__":
                continue

            # Check if there's a corresponding test
            has_test = base_name in test_targets

            explanation = _explanation_score(func, has_test)
            deficit = 1.0 - explanation

            # Weight by complexity
            complexity_factor = min(1.0, func.complexity / 20)
            weighted_score = deficit * complexity_factor

            # Dampen severity for short/simple functions (#151):
            # Functions with low LOC are less likely to hide critical debt.
            loc_factor = min(1.0, func.loc / 30)
            # Private functions (underscore-prefixed) are less critical
            # for external consumers to understand.
            is_private = base_name.startswith("_")
            visibility_factor = 0.7 if is_private else 1.0
            # Combine complexity-weighted deficit with LOC and visibility.
            weighted_score = weighted_score * (0.7 + 0.3 * loc_factor) * visibility_factor

            # Check AI attribution and defect correlation for this file (ADR-048)
            fpath_str = func.file_path.as_posix()
            history = file_histories.get(fpath_str)
            ai_related = history.ai_attributed_commits > 0 if history else False
            defect_correlated = history is not None and history.defect_correlated_commits > 0

            # Raise threshold for private functions — reduce noise on internal helpers.
            # Defect-correlated files always keep the lower threshold (actionable).
            min_threshold = 0.45 if is_private else 0.30
            if defect_correlated:
                min_threshold = min(min_threshold, 0.30)
            if weighted_score < min_threshold:
                continue

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

            missing = []
            if not func.has_docstring:
                missing.append("Docstring")
            if not has_test:
                missing.append("Tests")
            if not func.return_type:
                missing.append("Return-Type")
            fix = (
                (
                    f"Function {func.name} (complexity {func.complexity}): "
                    f"add {', '.join(missing)}."
                )
                if missing
                else None
            )

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
                    fix=fix,
                    metadata={
                        "function_name": func.name,
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
