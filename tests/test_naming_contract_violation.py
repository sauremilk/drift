"""Tests for NamingContractViolationSignal (NBV) — ADR-008."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.ast_parser import PythonFileParser
from drift.models import ParseResult, SignalType
from drift.signals.naming_contract_violation import NamingContractViolationSignal

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
            '''\
def validate_x(v):
    return v
''',
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
