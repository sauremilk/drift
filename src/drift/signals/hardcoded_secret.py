"""Signal: Hardcoded Secret Detection (HSC).

Detects hardcoded secrets, API tokens, and credentials in Python source
code by analysing AST assignment nodes for security-sensitive variable
names combined with string-literal values.

Uses a multi-layer approach:
1. Variable-name pattern matching (secret, key, token, password, etc.)
2. Known API token prefix detection (ghp_, sk-, AKIA, etc.)
3. Shannon entropy filtering for high-entropy strings

Maps to CWE-798 (Use of Hard-coded Credentials).

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter
from pathlib import Path

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
# Detection patterns
# ---------------------------------------------------------------------------

# Variable names that suggest credentials when assigned a string literal.
_SECRET_VAR_RE = re.compile(
    r"(?:secret|password|passwd|pwd|token|api_?key|apikey|auth_?token|"
    r"access_?key|private_?key|credential|db_?password|database_?password|"
    r"encryption_?key|signing_?key|jwt_?secret|client_?secret|"
    r"aws_?secret|secret_?key)",
    re.IGNORECASE,
)

# Known API token prefixes (high-confidence, no entropy check needed).
_KNOWN_PREFIXES: tuple[str, ...] = (
    "ghp_",       # GitHub personal access token
    "gho_",       # GitHub OAuth token
    "ghs_",       # GitHub server-to-server token
    "ghu_",       # GitHub user access token
    "github_pat_",  # GitHub fine-grained PAT
    "sk-",        # OpenAI / Stripe secret key
    "sk_live_",   # Stripe live secret
    "sk_test_",   # Stripe test secret
    "pk_live_",   # Stripe live publishable
    "pk_test_",   # Stripe test publishable
    "AKIA",       # AWS access key
    "xoxb-",      # Slack bot token
    "xoxp-",      # Slack user token
    "SG.",        # SendGrid API key
    "glpat-",     # GitLab PAT
)

# Values that are obviously placeholders, not real secrets.
_PLACEHOLDER_RE = re.compile(
    r"^(?:xxx+|\.\.\.+|changeme|change[-_]?me|your[-_]?secret[-_]?here|"
    r"replace[-_]?me|TODO|FIXME|INSERT[-_]?HERE|PLACEHOLDER|"
    r"example[-_]?secret|test[-_]?secret|dummy|sample|fake|mock|"
    r"<[^>]+>|\$\{[^}]+\})$",
    re.IGNORECASE,
)

# Safe RHS patterns: the value comes from env/config, not hardcoded.
_SAFE_CALL_NAMES: frozenset[str] = frozenset({
    "getenv",
    "environ",
    "get",
    "config",
    "Config",
    "Secret",
    "SecretStr",
})


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in freq.values()
    )


def _is_safe_value(node: ast.expr) -> bool:
    """Return True if the value node is a dynamic/env-sourced expression."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _SAFE_CALL_NAMES:
            return True
        if isinstance(func, ast.Name) and func.id in _SAFE_CALL_NAMES:
            return True
    if isinstance(node, ast.Subscript):
        # os.environ["KEY"]
        if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
            return True
        if isinstance(node.value, ast.Name) and node.value.id == "environ":
            return True
    # f-strings typically embed dynamic content
    return isinstance(node, ast.JoinedStr)


def _extract_string_value(node: ast.expr) -> str | None:
    """Extract a string literal from an AST node, if it is one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


@register_signal
class HardcodedSecretSignal(BaseSignal):
    """Detect hardcoded secrets and credentials in source code."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.HARDCODED_SECRET

    @property
    def name(self) -> str:
        return "Hardcoded Secret"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        findings: list[Finding] = []
        min_entropy = config.thresholds.hsc_min_entropy
        min_length = config.thresholds.hsc_min_length

        for pr in parse_results:
            if pr.language != "python":
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                repo_path = self._repo_path or Path(".")
                source = (repo_path / pr.file_path).read_text(
                    encoding="utf-8", errors="replace"
                )
                tree = ast.parse(source, filename=str(pr.file_path))
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                finding = self._check_assignment(
                    node, pr.file_path, min_entropy, min_length
                )
                if finding:
                    findings.append(finding)

        return findings

    def _check_assignment(
        self,
        node: ast.AST,
        file_path: Path,
        min_entropy: float,
        min_length: int,
    ) -> Finding | None:
        """Check a single AST node for hardcoded secret patterns."""
        # Handle: NAME = "value"
        if isinstance(node, ast.Assign):
            for target in node.targets:
                var_name = self._extract_var_name(target)
                if var_name and _SECRET_VAR_RE.search(var_name):
                    return self._evaluate_value(
                        node.value, var_name, file_path, node.lineno,
                        min_entropy, min_length,
                    )

        # Handle: NAME: type = "value"
        if isinstance(node, ast.AnnAssign) and node.value and node.target:
            var_name = self._extract_var_name(node.target)
            if var_name and _SECRET_VAR_RE.search(var_name):
                return self._evaluate_value(
                    node.value, var_name, file_path, node.lineno,
                    min_entropy, min_length,
                )

        # Handle keyword arguments: func(secret_key="value")
        if isinstance(node, ast.keyword) and node.arg and _SECRET_VAR_RE.search(node.arg):
            return self._evaluate_value(
                    node.value, node.arg, file_path,
                    getattr(node, "lineno", 0),
                    min_entropy, min_length,
                )

        return None

    @staticmethod
    def _extract_var_name(target: ast.expr) -> str | None:
        """Extract variable name from assignment target."""
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        return None

    def _evaluate_value(
        self,
        value_node: ast.expr,
        var_name: str,
        file_path: Path,
        lineno: int,
        min_entropy: float,
        min_length: int,
    ) -> Finding | None:
        """Evaluate whether the assigned value is a hardcoded secret."""
        if _is_safe_value(value_node):
            return None

        string_val = _extract_string_value(value_node)
        if string_val is None:
            return None

        # Skip empty / very short strings.
        if len(string_val) < 8:
            return None

        # Check for known API token prefixes (high confidence).
        for prefix in _KNOWN_PREFIXES:
            if string_val.startswith(prefix):
                return self._make_finding(
                    var_name, file_path, lineno,
                    rule_id="hardcoded_api_token",
                    score=0.9,
                    detail=f"Value starts with known API token prefix '{prefix}'.",
                )

        # Check for placeholder values.
        if _PLACEHOLDER_RE.match(string_val):
            return self._make_finding(
                var_name, file_path, lineno,
                rule_id="placeholder_secret",
                score=0.5,
                detail=(
                    "Placeholder secret detected. Replace with a "
                    "proper secret before deployment."
                ),
            )

        # Entropy-based detection for long strings.
        if len(string_val) >= min_length:
            entropy = _shannon_entropy(string_val)
            if entropy >= min_entropy:
                return self._make_finding(
                    var_name, file_path, lineno,
                    rule_id="hardcoded_secret",
                    score=0.7,
                    detail=(
                        f"High-entropy string ({entropy:.2f} bits/char) "
                        f"assigned to security-sensitive variable."
                    ),
                )

        # Catch remaining obvious cases (variable name matches, non-trivial string).
        if len(string_val) >= min_length:
            return self._make_finding(
                var_name, file_path, lineno,
                rule_id="hardcoded_secret",
                score=0.6,
                detail="String literal assigned to security-sensitive variable.",
            )

        return None

    def _make_finding(
        self,
        var_name: str,
        file_path: Path,
        lineno: int,
        *,
        rule_id: str,
        score: float,
        detail: str,
    ) -> Finding:
        severity = Severity.HIGH if score >= 0.6 else Severity.MEDIUM
        return Finding(
            signal_type=self.signal_type,
            severity=severity,
            score=score,
            title=f"Hardcoded secret in '{var_name}'",
            description=(
                f"{detail} "
                f"Variable '{var_name}' at {file_path}:{lineno} should use "
                f"environment variables or a secrets manager."
            ),
            file_path=file_path,
            start_line=lineno,
            end_line=lineno,
            symbol=var_name,
            fix=(
                f"Use os.environ['{var_name.upper()}'] or "
                f"os.getenv('{var_name.upper()}') instead of a string literal."
            ),
            metadata={
                "cwe": "CWE-798",
                "variable": var_name,
                "rule_id": rule_id,
            },
            rule_id=rule_id,
        )
