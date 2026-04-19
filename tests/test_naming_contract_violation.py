"""Tests for NamingContractViolationSignal (NBV) — ADR-008."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.ingestion.ast_parser import PythonFileParser
from drift.ingestion.ts_parser import parse_typescript_file, tree_sitter_available
from drift.models import ParseResult, SignalType
from drift.signals.naming_contract_violation import NamingContractViolationSignal

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**overrides: object) -> DriftConfig:
    thresholds = {}
    for k, v in overrides.items():
        thresholds[k] = v
    if thresholds:
        return DriftConfig(thresholds=thresholds)
    return DriftConfig()


def _write_and_parse(tmp_path: Path, rel: str, source: str) -> ParseResult:
    """Write a Python file, parse it, and return the ParseResult."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    parser = PythonFileParser(source, p)
    return parser.parse()


def _run(
    parse_results: list[ParseResult],
    repo_path: Path | None = None,
    **kw: object,
):
    sig = NamingContractViolationSignal(repo_path=repo_path)
    return sig.analyze(parse_results, {}, _cfg(**kw))


def _write_and_parse_ts(tmp_path: Path, rel: str, source: str) -> ParseResult:
    """Write a TS file and parse it with tree-sitter parser."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return parse_typescript_file(Path(rel), tmp_path, language="typescript")


# ===================================================================
# validate_* / check_* — expects raise or return False/None
# ===================================================================


class TestValidateRule:
    def test_validate_with_raise_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/validators.py",
            '''\
def validate_email(email: str) -> None:
    """Validate an email address."""
    if "@" not in email:
        raise ValueError("Invalid email")
    return None
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_validate_with_return_false_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/validators.py",
            '''\
def validate_token(token: str) -> bool:
    """Check token validity."""
    if not token:
        return False
    if len(token) < 10:
        return False
    return True
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_validate_without_rejection_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/validators.py",
            '''\
def validate_input(data: dict) -> dict:
    """Validate input data."""
    result = {}
    for key in data:
        result[key] = str(data[key])
    return result
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert findings[0].signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        assert "validate_" in findings[0].metadata["prefix_rule"]
        location = f"{findings[0].file_path.as_posix()}:{findings[0].start_line}"
        assert location in findings[0].fix
        assert "raise or return False/None" in findings[0].fix

    def test_check_without_rejection_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/validators.py",
            '''\
def check_permissions(user: object, resource: str) -> str:
    """Check user permissions."""
    name = getattr(user, "name", "anon")
    return f"{name} -> {resource}"
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "check_" in findings[0].metadata["prefix_rule"]

    @needs_tree_sitter
    def test_validate_ts_returns_error_string_or_null_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
            tmp_path,
            "src/validators.ts",
            """\
export function validateBaseUrl(input: string): string | null {
    if (!input.startsWith("https://")) {
        return "base url must start with https://";
    }
    return null;
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_validate_ts_returns_validation_object_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
            tmp_path,
            "src/validators.ts",
            """\
type ValidationResult = { valid: boolean; error?: string };

export function validateConfig(raw: Record<string, unknown>): ValidationResult {
    if (!raw["token"]) {
        return { valid: false, error: "missing token" };
    }
    return { valid: true };
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_check_ts_bare_return_void_rejection_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
            tmp_path,
            "src/validators.ts",
            """\
export function checkAuth(token?: string): void {
    if (!token) {
        return;
    }
    const ready = true;
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_check_ts_bare_return_non_void_no_crash_and_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
            tmp_path,
            "src/validators.ts",
            """\
export function checkAuth(token?: string): string {
    if (!token) {
        return;
    }
    return "ok";
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert len(nbv_findings) == 1
        assert nbv_findings[0].metadata.get("prefix_rule") == "check_"


# ===================================================================
# ensure_* — expects raise
# ===================================================================


class TestEnsureRule:
    def test_ensure_with_raise_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/guards.py",
            '''\
def ensure_connected(client: object) -> None:
    """Ensure client is connected."""
    if not getattr(client, "connected", False):
        raise ConnectionError("Not connected")
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_ensure_without_raise_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/guards.py",
            '''\
def ensure_directory(path: str) -> str:
    """Ensure directory exists."""
    import os
    os.makedirs(path, exist_ok=True)
    return path
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "ensure_" in findings[0].metadata["prefix_rule"]
        assert "add at least one raise path" in findings[0].fix

    @needs_tree_sitter
    def test_ensure_upsert_pattern_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "src/guards.ts",
                """\
export type JsonRecord = Record<string, unknown>;

export function ensureRecord(root: JsonRecord, key: string): JsonRecord {
    let next = root[key];
    if (next == null || typeof next !== "object" || Array.isArray(next)) {
        next = {};
        root[key] = next;
    }
    return next as JsonRecord;
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_without_throw_or_return_value_is_flagged(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "src/guards.ts",
                """\
export function ensureReady(flag: boolean): void {
    if (!flag) {
        return;
    }
    const state = "ready";
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert len(nbv_findings) == 1
        assert nbv_findings[0].metadata.get("prefix_rule") == "ensure_"

    @needs_tree_sitter
    def test_ensure_idempotent_mkdir_side_effect_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "src/fs_helpers.ts",
                """\
import * as fs from "node:fs";

export function ensureOutputRootDir(root: string): void {
    if (!fs.existsSync(root)) {
        fs.mkdirSync(root, { recursive: true });
    }
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_property_assignment_side_effect_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "src/dom_helpers.ts",
                """\
export function ensureShadowRoot(host: HTMLElement): void {
    if (!host.shadowRoot) {
        host.shadowRoot = host.attachShadow({ mode: "open" });
    }
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_registry_set_side_effect_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "src/registry.ts",
                """\
export function ensureThemeRegistered(registry: Map<string, object>, key: string): void {
    if (!registry.has(key)) {
        registry.set(key, {});
    }
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_ts_lazy_init_method_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "extensions/acpx/src/runtime.ts",
                """\
export type Session = { id: string };

export class AcpxRuntime {
    private session?: Session;

    private async createSession(): Promise<Session> {
        return { id: "s" };
    }

    async ensureSession(): Promise<Session> {
        if (!this.session) {
            this.session = await this.createSession();
        }
        return this.session;
    }
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_ts_delegated_raise_contract_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "extensions/acpx/src/runtime.ts",
                """\
export type SessionOptions = { id: string };
export type AcpRuntimeHandle = { id: string };

class RuntimeDelegate {
    async ensureSession(options: SessionOptions): Promise<AcpRuntimeHandle> {
        if (!options.id) {
            throw new Error("bad options");
        }
        return { id: options.id };
    }
}

export class Runtime {
    private delegate = new RuntimeDelegate();

    async ensureSession(options: SessionOptions): Promise<AcpRuntimeHandle> {
        return this.delegate.ensureSession(options);
    }
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []

    @needs_tree_sitter
    def test_ensure_ts_assertion_signature_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "extensions/browser/src/browser/assertions.ts",
                """\
type BrowserCtx = { connected: boolean };

export function ensureBrowserContext(ctx: BrowserCtx | null): asserts ctx is BrowserCtx {
    if (!ctx?.connected) {
        assertBrowserContext(ctx);
    }
}

declare function assertBrowserContext(ctx: BrowserCtx | null): asserts ctx is BrowserCtx;
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []


# ===================================================================
# is_* / has_* — expects bool return
# ===================================================================


class TestBoolRule:
    def test_is_with_bool_return_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/checks.py",
            '''\
def is_valid(value: str) -> bool:
    """Check if value is valid."""
    if not value:
        return False
    return True
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_has_with_bool_annotation_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/checks.py",
            '''\
def has_permission(user: object, action: str) -> bool:
    """Check if user has permission."""
    perms = getattr(user, "permissions", [])
    return action in perms
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_is_without_bool_return_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/checks.py",
            '''\
def is_admin(user: object) -> str:
    """Check admin status."""
    role = getattr(user, "role", "guest")
    return role
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "is_" in findings[0].metadata["prefix_rule"]
        assert "return a bool-compatible result" in findings[0].fix


# ===================================================================
# try_* — expects try/except
# ===================================================================


class TestTryRule:
    def test_try_with_exception_handling_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/ops.py",
            '''\
def try_connect(host: str, port: int) -> object:
    """Try to connect to host."""
    try:
        import socket
        s = socket.create_connection((host, port))
        return s
    except OSError:
        return None
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_try_without_exception_handling_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/ops.py",
            '''\
def try_parse(data: str) -> dict:
    """Try to parse data."""
    parts = data.split(",")
    result = {}
    for p in parts:
        k, v = p.split("=")
        result[k] = v
    return result
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "try_" in findings[0].metadata["prefix_rule"]

    def test_try_comparison_semantics_no_finding(self, tmp_path: Path):
        """Comparison-style try_* helpers should be treated as attempt semantics."""
        pr = _write_and_parse(
            tmp_path,
            "src/contracts.py",
            '''\
def try_neq_default(value: object, default: object) -> bool:
    """Attempt to decide whether value differs from default."""
    if value is None and default is None:
        return False
    return value != default
''',
        )

        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_try_in_utility_context_no_finding(self, tmp_path: Path):
        """Utility/helper module context should not force try/except semantics."""
        pr = _write_and_parse(
            tmp_path,
            "src/utils/contracts.py",
            '''\
def try_parse_config(raw: str) -> dict[str, str]:
    """Attempt a best-effort parse of key/value config."""
    pairs = raw.split(",")
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[key.strip()] = value.strip()
    return result
''',
        )

        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    @needs_tree_sitter
    def test_try_ts_nullable_getter_contract_no_finding(self, tmp_path: Path):
        pr = _write_and_parse_ts(
                tmp_path,
                "extensions/bluebubbles/src/runtime.ts",
                """\
export type BlueBubblesRuntime = { connected: boolean };

let globalRuntime: BlueBubblesRuntime | undefined;

export function tryGetBlueBubblesRuntime(): BlueBubblesRuntime | undefined {
    return globalRuntime ?? undefined;
}
""",
        )

        findings = _run([pr], repo_path=tmp_path)
        nbv_findings = [
            f for f in findings if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
        ]
        assert nbv_findings == []


# ===================================================================
# get_or_create_* — expects conditional + create path
# ===================================================================


class TestGetOrCreateRule:
    def test_get_or_create_with_branch_no_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/repo.py",
            '''\
def get_or_create_user(name: str, db: object) -> object:
    """Get or create a user."""
    user = db.get(name)
    if user is None:
        user = db.create(name)
    return user
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_get_or_create_without_create_finding(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/repo.py",
            '''\
def get_or_create_session(sid: str) -> dict:
    """Get or create session."""
    sessions = {"a": {}, "b": {}}
    return sessions.get(sid, {})
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1
        assert "get_or_create_" in findings[0].metadata["prefix_rule"]


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_private_function_ignored(self, tmp_path: Path):
        """Private functions (starting with _) should not be checked."""
        pr = _write_and_parse(
            tmp_path,
            "src/internal.py",
            '''\
def _validate_internal(data: dict) -> dict:
    """Internal validation helper."""
    result = {}
    for key in data:
        result[key] = data[key]
    return result
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_method_name_extracted(self, tmp_path: Path):
        """Class methods should be checked by their bare name."""
        pr = _write_and_parse(
            tmp_path,
            "src/service.py",
            '''\
class UserService:
    def validate_age(self, age: int) -> int:
        """Validate age."""
        # No rejection path
        return max(0, age)
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert len(findings) == 1

    def test_tiny_function_ignored(self, tmp_path: Path):
        """Functions below min LOC threshold should be skipped."""
        pr = _write_and_parse(
            tmp_path,
            "src/stubs.py",
            """\
def validate_x(v):
    return v
""",
        )
        # Default min LOC = 3; this function is 2 lines
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_test_file_ignored(self, tmp_path: Path):
        """Test files should be excluded entirely."""
        pr = _write_and_parse(
            tmp_path,
            "tests/test_validate.py",
            '''\
def validate_response(resp: dict) -> dict:
    """Test helper - not a real validator."""
    result = {}
    for key in resp:
        result[key] = resp[key]
    return result
''',
        )
        findings = _run([pr], repo_path=tmp_path)
        assert findings == []

    def test_no_python_files_no_findings(self):
        """Non-python files should produce no findings."""
        pr = ParseResult(
            file_path=Path("src/module.ts"),
            language="typescript",
            functions=[],
            classes=[],
            imports=[],
        )
        findings = _run([pr])
        assert findings == []


class TestLibraryContext:
    def test_library_layout_marks_context_candidate(self, tmp_path: Path):
        pr = _write_and_parse(
            tmp_path,
            "src/mylib/contracts.py",
            '''\
def validate_contract(payload: dict) -> dict:
    """Validate contract shape."""
    normalized = {}
    for key in payload:
        normalized[key] = payload[key]
    return normalized
''',
        )

        findings = _run([pr], repo_path=tmp_path)

        assert len(findings) == 1
        assert findings[0].metadata.get("library_context_candidate") is True


@needs_tree_sitter
class TestTypeScriptBoolRule:
        def test_async_bool_wrappers_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
export async function isSessionActive(): Promise<boolean> {
    return false;
}

export function hasPermission(): PromiseLike<boolean> {
    return Promise.resolve(true);
}

export function isObservableReady(): Observable<boolean> {
    return ready$;
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_async_non_bool_wrapper_is_flagged(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
export async function isSessionLabel(): Promise<string> {
    return "active";
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert len(nbv_findings) == 1
                assert nbv_findings[0].metadata.get("prefix_rule") == "is_"

        def test_type_predicate_return_type_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
type BrowserNode = { kind: "browser" };

export function isBrowserNode(node: unknown): node is BrowserNode {
    return typeof node === "object" && node !== null;
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_comparison_expression_without_annotation_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
export function isUsableTimestamp(input: unknown) {
    return typeof input === "number" && input > 0;
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_issue_265_is_prefix_inferred_bool_call_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "extensions/browser/src/browser/server-context.availability.ts",
                        """\
type Target = { url: string };

declare function probeReachability(target: Target): Promise<boolean>;

export async function isHttpReachable(target: Target) {
    return probeReachability(target);
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_issue_265_is_prefix_explicit_non_bool_still_flagged(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
export function isServerLabel(name: string) {
    return `${name}-prod`;
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert len(nbv_findings) == 1
                assert nbv_findings[0].metadata.get("prefix_rule") == "is_"

        def test_typed_arrow_declarator_return_type_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/checks.ts",
                        """\
export const hasConversation: (state: { messages: unknown[] }) => boolean = (state) => {
    return state.messages.length > 0;
};
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_boolean_or_expression_return_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "extensions/browser/src/browser-tool.ts",
                        """\
type TreeNode = { type: string };

export function isBrowserNode(node: TreeNode): boolean {
    return node.type === "browser" || node.type === "chromium";
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_issue_252_is_port_free_promise_boolean_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "extensions/qa-lab/src/docker-runtime.ts",
                        """\
import { createServer } from "node:net";

export async function isPortFree(port: number): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
        const server = createServer();
        server.once("error", () => resolve(false));
        server.once("listening", () => {
            server.close();
            resolve(true);
        });
        server.listen(port);
    });
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []

        def test_issue_252_validate_throw_no_finding(self, tmp_path: Path):
                pr = _write_and_parse_ts(
                        tmp_path,
                        "src/acp/control-plane/runtime-options.ts",
                        """\
export function validateNoControlChars(value: string, field: string): string {
    if (/[\\x00-\\x1f]/.test(value)) {
        throw new Error(`${field} contains control characters`);
    }
    return value;
}
""",
                )

                findings = _run([pr], repo_path=tmp_path)
                nbv_findings = [
                    f
                    for f in findings
                    if f.signal_type == SignalType.NAMING_CONTRACT_VIOLATION
                ]
                assert nbv_findings == []


# ---------------------------------------------------------------------------
# Negative property checks
# ---------------------------------------------------------------------------


class TestNBVNegativeProperties:
    """Verify that NBV signal outputs never contain None or invalid states."""

    def test_no_none_findings_for_violation(self, tmp_path: Path) -> None:
        pr = _write_and_parse(
            tmp_path, "utils.py",
            "def validate_user(x):\n    pass\n",
        )
        findings = _run([pr])
        assert not any(f is None for f in findings)
        assert not any(f.title is None for f in findings)

    def test_no_findings_for_empty_file(self, tmp_path: Path) -> None:
        pr = _write_and_parse(tmp_path, "empty.py", "# empty module\n")
        findings = _run([pr])
        assert not findings
        assert not any(f is None for f in findings)

    def test_findings_signal_type_not_none(self, tmp_path: Path) -> None:
        pr = _write_and_parse(
            tmp_path, "utils.py",
            "def get_data(): return None\n",
        )
        findings = _run([pr])
        assert not any(f.signal_type is None for f in findings)
        assert not any(f.severity is None for f in findings)

    def test_multiple_files_no_none(self, tmp_path: Path) -> None:
        pr1 = _write_and_parse(tmp_path, "a.py", "def compute_value(): pass\n")
        pr2 = _write_and_parse(tmp_path, "b.py", "def fetch_data(): pass\n")
        findings = _run([pr1, pr2])
        assert not any(f is None for f in findings)
        assert not any(f.file_path is None for f in findings)

    def test_no_none_for_class_methods(self, tmp_path: Path) -> None:
        pr = _write_and_parse(
            tmp_path, "models.py",
            "class User:\n    def validate_email(self):\n        pass\n",
        )
        findings = _run([pr])
        assert not any(f is None for f in findings)
        assert not any(f.score is None for f in findings)

    def test_empty_list_yields_no_findings(self) -> None:
        findings = _run([])
        assert not findings
        assert not any(f is None for f in findings)

    def test_findings_metadata_not_none(self, tmp_path: Path) -> None:
        pr = _write_and_parse(tmp_path, "svc.py", "def process_data(x): pass\n")
        findings = _run([pr])
        assert not any(f is None for f in findings)
        assert not any(f.metadata is None for f in findings)

    def test_no_findings_for_dunder_methods(self, tmp_path: Path) -> None:
        pr = _write_and_parse(
            tmp_path, "base.py",
            "class Base:\n    def __init__(self): pass\n    def __repr__(self): return ''\n",
        )
        findings = _run([pr])
        assert not any(f is None for f in findings)

    def test_findings_description_not_none(self, tmp_path: Path) -> None:
        pr = _write_and_parse(tmp_path, "utils.py", "def get_result(): return 42\n")
        findings = _run([pr])
        assert not any(f is None for f in findings)
        assert not any(f.description is None for f in findings)

    def test_findings_fix_not_raising(self, tmp_path: Path) -> None:
        pr = _write_and_parse(tmp_path, "utils.py", "def build_query(x): return x\n")
        findings = _run([pr])
        assert not any(f is None for f in findings)
