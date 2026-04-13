"""Signal: Insecure Default Detection (ISD).

Detects insecure configuration defaults commonly left behind by AI code
generators and tutorial copy-paste:

Python:
- ``DEBUG = True`` in non-test files
- ``ALLOWED_HOSTS = ["*"]`` / ``ALLOWED_HOSTS = []``
- ``CORS_ALLOW_ALL_ORIGINS = True`` / ``CORS_ORIGIN_ALLOW_ALL = True``
- ``SESSION_COOKIE_SECURE = False`` / ``CSRF_COOKIE_SECURE = False``
- ``SECURE_SSL_REDIRECT = False``
- ``verify=False`` in requests/httpx calls (SSL verification disabled)

TypeScript/JavaScript:
- ``cors({ origin: '*' })`` or ``cors({ origin: true })``
- ``secure: false`` in cookie/session configuration
- ``rejectUnauthorized: false`` disabling TLS verification

Maps to CWE-1188 (Initialization with an Insecure Default).

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import urlsplit

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import is_test_file
from drift.signals.base import BaseSignal, register_signal

# ---------------------------------------------------------------------------
# Insecure-default patterns (AST-based)
# ---------------------------------------------------------------------------


def _is_true(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_star_list(node: ast.expr) -> bool:
    """Check for ["*"] literal."""
    return (
        isinstance(node, ast.List)
        and len(node.elts) == 1
        and isinstance(node.elts[0], ast.Constant)
        and node.elts[0].value == "*"
    )


def _is_empty_list(node: ast.expr) -> bool:
    return isinstance(node, ast.List) and len(node.elts) == 0


# Each check returns (rule_id, title, description, fix, score) or None.
_AssignCheck = tuple[str, str, str, str, float]


def _check_debug_true(name: str, value: ast.expr) -> _AssignCheck | None:
    if name == "DEBUG" and _is_true(value):
        return (
            "insecure_debug_mode",
            "DEBUG mode enabled",
            "DEBUG = True exposes detailed error pages, stack traces, and "
            "internal configuration to any visitor.",
            "Set DEBUG = False or load from environment: "
            "DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'",
            0.8,
        )
    return None


def _check_allowed_hosts(name: str, value: ast.expr) -> _AssignCheck | None:
    if name == "ALLOWED_HOSTS":
        if _is_star_list(value):
            return (
                "insecure_allowed_hosts",
                "ALLOWED_HOSTS allows all domains",
                'ALLOWED_HOSTS = ["*"] disables host header validation, '
                "enabling HTTP host header attacks.",
                "Set ALLOWED_HOSTS to specific domain names for your deployment.",
                0.7,
            )
        if _is_empty_list(value):
            return (
                "insecure_allowed_hosts",
                "ALLOWED_HOSTS is empty",
                "ALLOWED_HOSTS = [] combined with DEBUG = False causes Django "
                "to reject all requests. Often indicates a placeholder config.",
                "Set ALLOWED_HOSTS to your deployment domains.",
                0.5,
            )
    return None


def _check_cors(name: str, value: ast.expr) -> _AssignCheck | None:
    if name in ("CORS_ALLOW_ALL_ORIGINS", "CORS_ORIGIN_ALLOW_ALL") and _is_true(value):
        return (
            "insecure_cors",
            "CORS allows all origins",
            f"{name} = True permits any domain to make cross-origin requests, "
            f"potentially exposing authenticated APIs to third-party sites.",
            f"Set {name} = False and use CORS_ALLOWED_ORIGINS with specific domains.",
            0.7,
        )
    return None


def _check_cookie_secure(name: str, value: ast.expr) -> _AssignCheck | None:
    if name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE") and _is_false(value):
        return (
            "insecure_cookie",
            f"{name} is False",
            f"{name} = False sends cookies over unencrypted HTTP, "
            f"exposing them to network interception.",
            f"Set {name} = True in production.",
            0.6,
        )
    return None


def _check_ssl_redirect(name: str, value: ast.expr) -> _AssignCheck | None:
    if name == "SECURE_SSL_REDIRECT" and _is_false(value):
        return (
            "insecure_ssl_redirect",
            "SSL redirect disabled",
            "SECURE_SSL_REDIRECT = False allows unencrypted HTTP connections.",
            "Set SECURE_SSL_REDIRECT = True in production.",
            0.5,
        )
    return None


_ASSIGN_CHECKS = [
    _check_debug_true,
    _check_allowed_hosts,
    _check_cors,
    _check_cookie_secure,
    _check_ssl_redirect,
]

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
_IGNORE_SECURITY_DIRECTIVE_RE = re.compile(
    r"^\s*#\s*drift:ignore-security(?:\s|$)",
    re.IGNORECASE,
)


def _check_verify_false(node: ast.keyword) -> _AssignCheck | None:
    """Detect verify=False in HTTP library calls."""
    if node.arg == "verify" and _is_false(node.value):
        return (
            "insecure_ssl_verify",
            "SSL verification disabled",
            "verify=False disables TLS certificate validation, "
            "making the connection vulnerable to man-in-the-middle attacks.",
            "Remove verify=False or set verify=True. "
            "For self-signed certs, pass a CA bundle path instead.",
            0.7,
        )
    return None


def _call_targets_loopback(node: ast.Call) -> bool:
    """Return True when the first call argument targets localhost/loopback."""
    if not node.args:
        return False
    first_arg = node.args[0]
    if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
        return False

    target = first_arg.value.strip()
    if not target.lower().startswith(("http://", "https://")):
        return False

    try:
        parsed = urlsplit(target)
    except ValueError:
        return False

    host = (parsed.hostname or "").lower()
    return host in _LOOPBACK_HOSTS or host.endswith(".localhost")


def _has_ignore_security_directive(source: str) -> bool:
    """Return True if module header contains explicit ignore-security directive."""
    return any(_IGNORE_SECURITY_DIRECTIVE_RE.search(line) for line in source.split("\n")[:5])


@register_signal
class InsecureDefaultSignal(BaseSignal):
    """Detect insecure configuration defaults."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.INSECURE_DEFAULT

    @property
    def name(self) -> str:
        return "Insecure Default"

    _TS_LANGS = frozenset({"typescript", "tsx", "javascript", "jsx"})

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        findings: list[Finding] = []

        for pr in parse_results:
            if is_test_file(pr.file_path):
                continue

            if pr.language == "python":
                # Skip conftest.py (test infrastructure)
                if pr.file_path.name == "conftest.py":
                    continue
                self._analyze_python(pr, findings)
            elif pr.language in self._TS_LANGS:
                self._analyze_typescript(pr, findings)

        return findings

    # ------------------------------------------------------------------
    # Python analysis (AST-based)
    # ------------------------------------------------------------------

    def _analyze_python(
        self,
        pr: ParseResult,
        findings: list[Finding],
    ) -> None:
        repo_path = self._repo_path or Path(".")
        try:
            source = (repo_path / pr.file_path).read_text(
                encoding="utf-8", errors="replace"
            )
            tree = ast.parse(source, filename=str(pr.file_path))
        except (OSError, SyntaxError):
            return

        self._check_tree(tree, pr.file_path, source, findings)

    # ------------------------------------------------------------------
    # TypeScript / JavaScript analysis (regex-based)
    # ------------------------------------------------------------------

    # Patterns for TS/JS insecure defaults (line-level regex)
    _TS_CORS_WILDCARD_RE = re.compile(
        r"""cors\s*\(\s*\{[^}]*origin\s*:\s*['"]?\*['"]?""",
        re.IGNORECASE,
    )
    _TS_CORS_ALLOW_ALL_RE = re.compile(
        r"""cors\s*\(\s*\{[^}]*origin\s*:\s*true""",
        re.IGNORECASE,
    )
    _TS_REJECT_UNAUTH_RE = re.compile(
        r"""rejectUnauthorized\s*:\s*false""",
    )
    _TS_COOKIE_INSECURE_RE = re.compile(
        r"""secure\s*:\s*false""",
    )

    def _analyze_typescript(
        self,
        pr: ParseResult,
        findings: list[Finding],
    ) -> None:
        repo_path = self._repo_path or Path(".")
        try:
            source = (repo_path / pr.file_path).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return

        if _has_ignore_security_directive(source):
            return

        for lineno, line in enumerate(source.splitlines(), start=1):
            if self._TS_CORS_WILDCARD_RE.search(line):
                findings.append(self._make_finding(
                    "insecure_cors",
                    "CORS allows all origins",
                    "cors({ origin: '*' }) permits any domain to make cross-origin "
                    "requests, potentially exposing authenticated APIs.",
                    "Set origin to a specific list of allowed domains.",
                    0.7, pr.file_path, lineno,
                ))
            elif self._TS_CORS_ALLOW_ALL_RE.search(line):
                findings.append(self._make_finding(
                    "insecure_cors",
                    "CORS allows all origins",
                    "cors({ origin: true }) permits any domain to make cross-origin "
                    "requests.",
                    "Set origin to a specific list of allowed domains.",
                    0.7, pr.file_path, lineno,
                ))

            if self._TS_REJECT_UNAUTH_RE.search(line):
                findings.append(self._make_finding(
                    "insecure_ssl_verify",
                    "TLS verification disabled",
                    "rejectUnauthorized: false disables TLS certificate validation, "
                    "making the connection vulnerable to man-in-the-middle attacks.",
                    "Remove rejectUnauthorized: false or set to true. "
                    "For self-signed certs, use a custom CA.",
                    0.7, pr.file_path, lineno,
                ))

            if self._TS_COOKIE_INSECURE_RE.search(line):
                # Only flag if it looks like session/cookie config context.
                lower_line = line.lower()
                if any(kw in lower_line for kw in ("cookie", "session", "express-session")):
                    findings.append(self._make_finding(
                        "insecure_cookie",
                        "Insecure cookie configuration",
                        "secure: false sends cookies over unencrypted HTTP, "
                        "exposing them to network interception.",
                        "Set secure: true in production cookie configuration.",
                        0.6, pr.file_path, lineno,
                    ))

    def _check_tree(
        self,
        tree: ast.Module,
        file_path: Path,
        source: str,
        findings: list[Finding],
    ) -> None:
        # Check for drift:ignore-security comment at module level.
        if _has_ignore_security_directive(source):
            return

        for node in ast.walk(tree):
            # Simple assignments: NAME = value
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    name = self._target_name(target)
                    if name:
                        self._run_assign_checks(
                            name, node.value, file_path, node.lineno, findings
                        )

            # Annotated assignments: NAME: type = value
            if isinstance(node, ast.AnnAssign) and node.value and node.target:
                name = self._target_name(node.target)
                if name:
                    self._run_assign_checks(
                        name, node.value, file_path, node.lineno, findings
                    )

            # Keyword arguments: func(verify=False)
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    result = _check_verify_false(kw)
                    if result:
                        rule_id, title, desc, fix, score = result
                        if _call_targets_loopback(node):
                            rule_id = "insecure_ssl_verify_localhost"
                            title = "SSL verification disabled for localhost target"
                            desc = (
                                "verify=False disables TLS certificate validation. "
                                "The detected target appears to be localhost/loopback, "
                                "so severity is reduced for local-dev context."
                            )
                            fix = (
                                "Prefer verify=True even for local endpoints. "
                                "If local testing requires verify=False, keep it narrowly "
                                "scoped and document why."
                            )
                            score = 0.45
                        findings.append(
                            self._make_finding(
                                rule_id, title, desc, fix, score,
                                file_path,
                                getattr(kw, "lineno", node.lineno),
                            )
                        )

    @staticmethod
    def _target_name(target: ast.expr) -> str | None:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        return None

    def _run_assign_checks(
        self,
        name: str,
        value: ast.expr,
        file_path: Path,
        lineno: int,
        findings: list[Finding],
    ) -> None:
        for check in _ASSIGN_CHECKS:
            result = check(name, value)
            if result:
                rule_id, title, desc, fix, score = result
                findings.append(
                    self._make_finding(rule_id, title, desc, fix, score, file_path, lineno)
                )

    def _make_finding(
        self,
        rule_id: str,
        title: str,
        description: str,
        fix: str,
        score: float,
        file_path: Path,
        lineno: int,
    ) -> Finding:
        severity = Severity.HIGH if score >= 0.6 else Severity.MEDIUM
        return Finding(
            signal_type=self.signal_type,
            severity=severity,
            score=score,
            title=title,
            description=description,
            file_path=file_path,
            start_line=lineno,
            end_line=lineno,
            fix=fix,
            metadata={
                "cwe": "CWE-1188",
                "rule_id": rule_id,
            },
            rule_id=rule_id,
        )
