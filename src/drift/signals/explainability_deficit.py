"""Signal 4: Explainability Deficit Score (EDS).

Detects functions with high complexity but insufficient documentation,
test coverage indicators, or commit rationale — especially when
AI-attributed, indicating "accepted without understanding."
"""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context
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


def _has_self_documenting_ts_signature(func: FunctionInfo) -> bool:
    """Return True when TS/TSX signatures already communicate intent well."""
    if func.language not in ("typescript", "tsx") or not func.parameters:
        return False

    # Treat signatures as self-documenting only when parameter types are
    # explicitly declared and not dominated by generic `any` annotations.
    for parameter in func.parameters:
        lowered = parameter.lower()
        if ":" not in parameter:
            return False
        if "any" in lowered:
            return False

    return True


def _is_ts_ui_implementation_context(func: FunctionInfo) -> bool:
    """Return True for TS/TSX paths or names that suggest internal UI wiring."""
    if func.language not in ("typescript", "tsx"):
        return False

    file_posix = func.file_path.as_posix().lower()
    path_markers = (
        "/web/",
        "/ui/",
        "/views/",
        "/view/",
        "/dom/",
        "/components/",
        "/component/",
        "app.ts",
        "app.tsx",
        "ui-render",
        "render",
        "binding",
        "wizard",
    )
    if any(marker in file_posix for marker in path_markers):
        return True

    function_name = func.name.lower()
    return function_name.startswith(("render", "bind", "refresh", "mount", "hydrate"))


def _is_ts_js_family(language: str) -> bool:
    return language in ("typescript", "tsx", "javascript", "jsx")


def _ts_test_file_candidates(file_path: Path) -> set[Path]:
    """Return common colocated test file candidates for TS/JS source files."""
    suffix = file_path.suffix
    stem = file_path.stem
    parent = file_path.parent

    candidates = {
        parent / f"{stem}.test{suffix}",
        parent / f"{stem}.spec{suffix}",
        parent / "__tests__" / f"{stem}.test{suffix}",
        parent / "__tests__" / f"{stem}.spec{suffix}",
    }

    parts = file_path.parts
    if "src" in parts:
        src_index = parts.index("src")
        rel_after_src = Path(*parts[src_index + 1 :]) if src_index + 1 < len(parts) else Path()
        tests_root = Path(*parts[:src_index], "tests")
        tests_base = tests_root / rel_after_src.parent
        candidates.update(
            {
                tests_base / f"{stem}.test{suffix}",
                tests_base / f"{stem}.spec{suffix}",
                tests_base / "__tests__" / f"{stem}.test{suffix}",
                tests_base / "__tests__" / f"{stem}.spec{suffix}",
            }
        )

    return candidates


def _has_mapped_ts_test_file(
    file_path: Path,
    repo_path: Path | None,
    known_test_paths: set[str],
) -> bool | None:
    """Return TS/JS test evidence from path mapping.

    Returns:
    - True: matching test file was found
    - False: mapping checked with filesystem access and no test file exists
    - None: mapping could not be verified (e.g. missing repo_path)
    """
    candidates = _ts_test_file_candidates(file_path)
    candidate_posix = {candidate.as_posix().lower() for candidate in candidates}
    if any(candidate in known_test_paths for candidate in candidate_posix):
        return True

    if repo_path is None:
        return None

    return any((repo_path / candidate).is_file() for candidate in candidates)


def _explanation_score(
    func: FunctionInfo,
    has_test: bool | None,
    *,
    self_documenting_signature: bool = False,
) -> float:
    """Calculate how well-explained a function is (0.0=unexplained, 1.0=well-explained)."""
    evidence = 0.0
    max_evidence = 4.0 if has_test is not None else 2.5

    if func.has_docstring:
        evidence += 1.0
    elif self_documenting_signature:
        # In TS/TSX, typed signatures often provide the core API explanation.
        evidence += 1.0

    if has_test is True:
        evidence += 1.5

    # Decorators suggest framework integration (router, property, etc.)
    if func.decorators:
        evidence += 0.5

    # Return type annotation suggests intentional design
    if func.return_type:
        evidence += 1.0
    elif self_documenting_signature:
        # TS frequently relies on inferred return types from typed parameters/body.
        evidence += 0.5

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
        known_test_paths: set[str] = set()
        ts_test_mapping_cache: dict[str, bool | None] = {}

        for pr in parse_results:
            if classify_file_context(pr.file_path) == "test":
                known_test_paths.add(pr.file_path.as_posix().lower())
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
        handling = config.test_file_handling or "reduce_severity"

        for _key, func in all_functions.items():
            # Skip test files and trivial functions
            path_context = classify_file_context(func.file_path)
            if path_context == "test" and handling == "exclude":
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
            has_test: bool | None = base_name in test_targets
            if not has_test and _is_ts_js_family(func.language):
                file_key = func.file_path.as_posix().lower()
                mapped_has_test = ts_test_mapping_cache.get(file_key)
                if mapped_has_test is None and file_key not in ts_test_mapping_cache:
                    mapped_has_test = _has_mapped_ts_test_file(
                        func.file_path,
                        self.repo_path,
                        known_test_paths,
                    )
                    ts_test_mapping_cache[file_key] = mapped_has_test
                else:
                    mapped_has_test = ts_test_mapping_cache.get(file_key)

                if mapped_has_test is True:
                    has_test = True
                elif mapped_has_test is None:
                    has_test = None
            self_documenting_signature = _has_self_documenting_ts_signature(func)

            explanation = _explanation_score(
                func,
                has_test,
                self_documenting_signature=self_documenting_signature,
            )
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
            if self_documenting_signature:
                # Reduce false positives for typed TS/TSX signatures where JSDoc is optional.
                weighted_score *= 0.75
            if path_context == "test" and handling == "reduce_severity":
                weighted_score *= 0.5

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
            # ADR-077: further raise threshold for private micro-helpers (LOC < 40,
            # no defect correlation) — avoids CXS→EDS oscillation in fix-loops
            # where freshly-extracted private helpers trigger EDS before docs are added.
            if is_private and func.loc < 40 and not defect_correlated:
                min_threshold = max(min_threshold, 0.55)
            if weighted_score < min_threshold:
                continue

            severity = Severity.INFO
            if weighted_score >= 0.7:
                severity = Severity.HIGH
            elif weighted_score >= 0.5:
                severity = Severity.MEDIUM
            elif weighted_score >= 0.3:
                severity = Severity.LOW

            if path_context == "test" and handling == "reduce_severity":
                severity = Severity.LOW

            ts_ui_high_cap_applied = False
            is_ts_internal_impl = (
                func.language in ("typescript", "tsx")
                and not func.is_exported
                and not func.has_docstring
                and not self_documenting_signature
            )
            if severity == Severity.HIGH and (
                is_ts_internal_impl or _is_ts_ui_implementation_context(func)
            ):
                # Issue #258: avoid escalating internal TS UI wiring code to HIGH
                # solely due to missing JSDoc when complexity is large.
                severity = Severity.MEDIUM
                weighted_score = min(weighted_score, 0.69)
                ts_ui_high_cap_applied = True

            desc_parts = [
                f"Complexity: {func.complexity}, LOC: {func.loc}.",
            ]
            if not func.has_docstring and not self_documenting_signature:
                desc_parts.append("No docstring.")
            if has_test is False:
                desc_parts.append("No corresponding test found.")
            elif has_test is None:
                desc_parts.append("Test coverage status unknown.")
            if not func.return_type and not self_documenting_signature:
                desc_parts.append("No return type annotation.")
            if ai_related:
                desc_parts.append("File contains AI-attributed commits.")

            missing = []
            if not func.has_docstring and not self_documenting_signature:
                missing.append("Docstring")
            if has_test is False:
                missing.append("Tests")
            if not func.return_type and not self_documenting_signature:
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
                        "has_test_unknown": has_test is None,
                        "has_return_type": func.return_type is not None,
                        "self_documenting_signature": self_documenting_signature,
                        "explanation_score": round(explanation, 3),
                        "ts_ui_high_cap_applied": ts_ui_high_cap_applied,
                        "finding_context": path_context,
                    },
                    finding_context=path_context,
                )
            )

        return findings
