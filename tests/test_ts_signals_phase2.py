"""Tests for Phase 2 TypeScript signal support (GCD, BEM, NBV).

Verifies that GuardClauseDeficit, BroadExceptionMonoculture, and
NamingContractViolation correctly process TypeScript/JavaScript parse
results.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import (
    FunctionInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
    SignalType,
)
from drift.signals.broad_exception_monoculture import BroadExceptionMonocultureSignal
from drift.signals.guard_clause_deficit import GuardClauseDeficitSignal
from drift.signals.naming_contract_violation import NamingContractViolationSignal

ts_available: bool
try:
    import tree_sitter  # noqa: F401
    import tree_sitter_typescript  # noqa: F401

    ts_available = True
except ImportError:
    ts_available = False

needs_tree_sitter = pytest.mark.skipif(
    not ts_available, reason="tree-sitter-typescript not installed"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**overrides: object) -> DriftConfig:
    thresholds = {}
    for k, v in overrides.items():
        thresholds[k] = v
    return DriftConfig(thresholds=thresholds) if thresholds else DriftConfig()


def _ts_func(
    name: str,
    file_path: Path,
    *,
    params: list[str] | None = None,
    complexity: int = 6,
    loc: int = 10,
    start_line: int = 1,
    end_line: int = 10,
    return_type: str | None = None,
    decorators: list[str] | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language="typescript",
        complexity=complexity,
        loc=loc,
        parameters=params if params is not None else ["data", "config", "mode"],
        return_type=return_type,
        decorators=decorators or [],
        has_docstring=False,
        body_hash="abc123",
        ast_fingerprint={},
    )


def _ts_parse_result(
    file_path: Path,
    functions: list[FunctionInfo] | None = None,
    patterns: list[PatternInstance] | None = None,
    language: str = "typescript",
) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language=language,
        functions=functions or [],
        classes=[],
        imports=[],
        patterns=patterns or [],
    )


def _handler(exc_type: str = "Exception", actions: list[str] | None = None) -> dict:
    return {
        "exception_type": exc_type,
        "actions": actions if actions is not None else ["pass"],
    }


def _pattern(file_path: Path, handlers: list[dict]) -> PatternInstance:
    return PatternInstance(
        category=PatternCategory.ERROR_HANDLING,
        file_path=file_path,
        function_name="handler",
        start_line=1,
        end_line=10,
        fingerprint={"handlers": handlers},
    )


def _write_ts(tmp_path: Path, rel: str, source: str) -> Path:
    """Write a file and return its path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


# ===================================================================
# GCD — Guard Clause Deficit (TypeScript)
# ===================================================================


class TestGCDTypeScript:
    """TypeScript support for GuardClauseDeficitSignal."""

    def _run(self, prs: list[ParseResult], repo_path: Path | None = None, **kw):
        sig = GuardClauseDeficitSignal(repo_path=repo_path)
        return sig.analyze(prs, {}, _cfg(**kw))

    def test_ts_unsupported_language_skipped(self):
        """Rust (unsupported) should be silently ignored."""
        fp = Path("src/mod/lib.rs")
        fn = _ts_func("handle", fp)
        fn = FunctionInfo(**{**fn.__dict__, "language": "rust"})
        pr = _ts_parse_result(fp, functions=[fn], language="rust")
        assert self._run([pr]) == []

    @needs_tree_sitter
    def test_ts_guarded_functions_no_finding(self, tmp_path: Path):
        """TS functions with if-throw guards should not trigger."""
        source = """\
function processData(data: any, config: object, mode: string): void {
    if (!data) throw new Error("data required");
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    }
}

function processMore(data: any, config: object, mode: string): void {
    if (data === null) return;
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    }
}

function processThird(data: any, config: object, mode: string): void {
    if (typeof data !== "object") throw new TypeError("expected object");
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    }
}

function processFourth(data: any, config: object, mode: string): void {
    if (!config) throw new Error("config required");
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/guarded.ts", source)

        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")

        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_unguarded_functions_triggers(self, tmp_path: Path):
        """TS functions without guards should trigger a finding."""
        source = """\
function handleA(data: any, config: object, mode: string): void {
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    } else if (mode === "d") {
        console.debug(x);
    }
}

function handleB(data: any, config: object, mode: string): void {
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    } else if (mode === "d") {
        console.debug(x);
    }
}

function handleC(data: any, config: object, mode: string): void {
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    } else if (mode === "d") {
        console.debug(x);
    }
}

function handleD(data: any, config: object, mode: string): void {
    const x = data;
    if (mode === "a") {
        console.log(x);
    } else if (mode === "b") {
        console.warn(x);
    } else if (mode === "c") {
        console.error(x);
    } else if (mode === "d") {
        console.debug(x);
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/unguarded.ts", source)

        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")

        findings = self._run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.GUARD_CLAUSE_DEFICIT

    @needs_tree_sitter
    def test_ts_index_file_excluded(self, tmp_path: Path):
        """index.ts should be excluded like __init__.py."""
        source = """\
function handleA(data: any, config: object, mode: string): void {
    const x = data;
    if (mode === "a") { console.log(x); }
    else if (mode === "b") { console.warn(x); }
    else if (mode === "c") { console.error(x); }
    else if (mode === "d") { console.debug(x); }
}
"""
        # Repeat 4 times for min_public threshold
        full_source = source * 4
        full_source = full_source.replace("handleA", "handleA", 1)
        # Actually write 4 separate functions
        funcs = ""
        for i in "ABCD":
            funcs += f"""\
function handle{i}(data: any, config: object, mode: string): void {{
    const x = data;
    if (mode === "a") {{ console.log(x); }}
    else if (mode === "b") {{ console.warn(x); }}
    else if (mode === "c") {{ console.error(x); }}
    else if (mode === "d") {{ console.debug(x); }}
}}

"""
        fp = _write_ts(tmp_path, "src/mod/index.ts", funcs)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")

        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    def test_ts_test_file_excluded(self):
        """TS test files should be excluded."""
        fp = Path("src/mod/service.test.ts")
        fns = [_ts_func(f"handle_{i}", fp) for i in range(4)]
        pr = _ts_parse_result(fp, functions=fns)
        assert self._run([pr]) == []


# ===================================================================
# BEM — Broad Exception Monoculture (TypeScript broad types)
# ===================================================================


class TestBEMTypeScript:
    """TypeScript broad exception types for BEM."""

    def _run(self, prs: list[ParseResult], **kw):
        sig = BroadExceptionMonocultureSignal()
        return sig.analyze(prs, {}, _cfg(**kw))

    def test_ts_bare_catch_detected(self):
        """Bare catch (no type annotation) should count as broad."""
        fp = Path("src/mod/handlers.ts")
        handlers = [_handler("bare", ["pass"])] * 4
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_ts_any_catch_detected(self):
        """catch(e: any) should count as broad."""
        fp = Path("src/mod/handlers.ts")
        handlers = [_handler("any", ["log"])] * 4
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_ts_unknown_catch_detected(self):
        """catch(e: unknown) should count as broad."""
        fp = Path("src/mod/handlers.ts")
        handlers = [_handler("unknown", ["pass"])] * 4
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_ts_error_catch_detected(self):
        """catch(e: Error) should count as broad."""
        fp = Path("src/mod/handlers.ts")
        handlers = [_handler("Error", ["log"])] * 4
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert len(findings) == 1

    def test_ts_specific_catch_not_broad(self):
        """Specific TS error types should NOT count as broad."""
        fp = Path("src/mod/handlers.ts")
        handlers = [
            _handler("TypeError", ["log"]),
            _handler("RangeError", ["log"]),
            _handler("SyntaxError", ["log"]),
            _handler("ReferenceError", ["log"]),
        ]
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        assert findings == []

    def test_ts_mixed_broad_and_specific(self):
        """Mixed broad+specific handlers — ratio below threshold → no finding."""
        fp = Path("src/mod/handlers.ts")
        handlers = [
            _handler("any", ["pass"]),
            _handler("TypeError", ["throw"]),
            _handler("RangeError", ["throw"]),
            _handler("SyntaxError", ["throw"]),
            _handler("ReferenceError", ["throw"]),
        ]
        pr = _ts_parse_result(fp, patterns=[_pattern(fp, handlers)])
        findings = self._run([pr])
        # 1/5 broad = 0.2 → below 0.80 threshold → no finding
        assert findings == []


# ===================================================================
# NBV — Naming Contract Violation (TypeScript)
# ===================================================================


class TestNBVTypeScript:
    """TypeScript support for NamingContractViolationSignal."""

    def _run(self, prs: list[ParseResult], repo_path: Path | None = None, **kw):
        sig = NamingContractViolationSignal(repo_path=repo_path)
        return sig.analyze(prs, {}, _cfg(**kw))

    @needs_tree_sitter
    def test_ts_validate_with_throw_no_finding(self, tmp_path: Path):
        source = """\
function validateEmail(email: string): void {
    if (!email.includes("@")) {
        throw new Error("Invalid email");
    }
    return;
}
"""
        fp = _write_ts(tmp_path, "src/validators.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_validate_without_throw_finding(self, tmp_path: Path):
        source = """\
function validateInput(data: Record<string, any>, schema: object): Record<string, any> {
    const result: Record<string, any> = {};
    for (const key of Object.keys(data)) {
        result[key] = String(data[key]);
    }
    return result;
}
"""
        fp = _write_ts(tmp_path, "src/validators.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        assert (
            "validate_" in findings[0].metadata["prefix_rule"]
            or "validateInput" in findings[0].title
        )

    @needs_tree_sitter
    def test_ts_is_with_boolean_return_no_finding(self, tmp_path: Path):
        source = """\
function isValid(value: string): boolean {
    if (!value) {
        return false;
    }
    return true;
}
"""
        fp = _write_ts(tmp_path, "src/checks.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_is_without_boolean_return_finding(self, tmp_path: Path):
        source = """\
function isAdmin(user: Record<string, any>, context: object): string {
    const role = user["role"] || "guest";
    return role;
}
"""
        fp = _write_ts(tmp_path, "src/checks.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "is_" in findings[0].metadata["prefix_rule"]

    @needs_tree_sitter
    def test_ts_ensure_with_throw_no_finding(self, tmp_path: Path):
        source = """\
function ensureConnected(client: any, options: any): void {
    if (!client.connected) {
        throw new Error("Not connected");
    }
    return;
}
"""
        fp = _write_ts(tmp_path, "src/guards.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_try_with_try_catch_no_finding(self, tmp_path: Path):
        source = """\
function tryConnect(host: string, port: number): boolean {
    try {
        const conn = connect(host, port);
        return true;
    } catch (e) {
        return false;
    }
}
"""
        fp = _write_ts(tmp_path, "src/network.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_try_with_promise_catch_no_finding(self, tmp_path: Path):
        source = """\
async function tryConnect(host: string): Promise<Connection | null> {
    return connect(host).catch(() => null);
}
"""
        fp = _write_ts(tmp_path, "src/network.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_try_with_optional_chain_and_fallback_no_finding(self, tmp_path: Path):
        source = """\
function tryGetTheme(config: AppConfig | undefined): Theme {
    return config?.settings?.theme ?? defaultTheme;
}
"""
        fp = _write_ts(tmp_path, "src/network.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_try_with_conditional_early_fallback_no_finding(self, tmp_path: Path):
        source = """\
function tryGetRuntime(runtime: Runtime | undefined): Runtime | undefined {
    if (!runtime?.isAvailable) {
        return undefined;
    }
    return runtime.getInstance();
}
"""
        fp = _write_ts(tmp_path, "src/network.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_ts_try_without_recovery_pattern_still_finding(self, tmp_path: Path):
        source = """\
function tryConnect(host: string): Connection {
    return connect(host);
}
"""
        fp = _write_ts(tmp_path, "src/network.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        findings = self._run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        assert findings[0].metadata.get("prefix_rule") == "try_"

    def test_ts_test_file_excluded(self):
        """TS test files should be excluded from NBV analysis."""
        fp = Path("src/validators.test.ts")
        fns = [_ts_func("validateEmail", fp, loc=10)]
        pr = _ts_parse_result(fp, functions=fns)
        assert self._run([pr]) == []

    def test_ts_unsupported_language_skipped(self):
        """Unsupported languages should be silently ignored."""
        fp = Path("src/validators.rs")
        fn = _ts_func("validateEmail", fp)
        fn = FunctionInfo(**{**fn.__dict__, "language": "rust"})
        pr = _ts_parse_result(fp, functions=[fn], language="rust")
        assert self._run([pr]) == []


# ===================================================================
# TS parser catch clause type extraction
# ===================================================================


class TestTSParserCatchTypes:
    """Verify that the TS parser correctly extracts exception types."""

    @needs_tree_sitter
    def test_bare_catch_is_bare(self, tmp_path: Path):
        source = """\
function foo(): void {
    try {
        doSomething();
    } catch {
        console.log("error");
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/bare.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        handlers = pr.patterns[0].fingerprint["handlers"]
        assert handlers[0]["exception_type"] == "bare"

    @needs_tree_sitter
    def test_untyped_catch_is_bare(self, tmp_path: Path):
        source = """\
function foo(): void {
    try {
        doSomething();
    } catch (e) {
        console.log(e);
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/untyped.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        handlers = pr.patterns[0].fingerprint["handlers"]
        assert handlers[0]["exception_type"] == "bare"

    @needs_tree_sitter
    def test_any_catch_extracted(self, tmp_path: Path):
        source = """\
function foo(): void {
    try {
        doSomething();
    } catch (e: any) {
        console.log(e);
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/anytype.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        handlers = pr.patterns[0].fingerprint["handlers"]
        assert handlers[0]["exception_type"] == "any"

    @needs_tree_sitter
    def test_error_type_extracted(self, tmp_path: Path):
        source = """\
function foo(): void {
    try {
        doSomething();
    } catch (e: Error) {
        console.log(e.message);
    }
}
"""
        fp = _write_ts(tmp_path, "src/mod/error.ts", source)
        from drift.ingestion.ts_parser import parse_typescript_file

        pr = parse_typescript_file(fp, "typescript")
        handlers = pr.patterns[0].fingerprint["handlers"]
        assert handlers[0]["exception_type"] == "Error"
