"""Signal: Hardcoded Secret Detection (HSC).

Detects hardcoded secrets, API tokens, and credentials in Python and
TypeScript/JavaScript source code by analysing AST assignment nodes for
security-sensitive variable names combined with string-literal values.

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
from urllib.parse import urlsplit

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context
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

_MESSAGE_SUFFIX_RE = re.compile(r"(?:_|^)(?:error|warning|message)$", re.IGNORECASE)

_ML_TOKENIZER_BASE_NAMES: frozenset[str] = frozenset({
    "pad",
    "cls",
    "sep",
    "mask",
    "eos",
    "bos",
    "unk",
    "audio",
    "video",
    "message_start",
    "message_end",
    "image",
    "vision",
    "special",
})

_ML_TOKENIZER_SYMBOL_NAMES: frozenset[str] = frozenset({
    "chat_template",
    "tokenizer_class",
    "tokenizer_class_name",
})

_SYMBOL_DECLARATION_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:-]{2,}$")

_OTEL_GENAI_SEMCONV_RE = re.compile(r"^gen_ai\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$")

_ENV_PLACEHOLDER_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")

_ENV_VAR_NAME_LITERAL_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")

_ENV_NAME_VAR_SUFFIXES: tuple[str, ...] = (
    "_ENV",
    "_ENV_KEY",
    "_KEY_ENV",
    "_VAR",
)

_MARKER_CONST_NAME_RE = re.compile(
    r"(?:^|_)(?:marker|prefix|alphabet|message|error_code)(?:_|$)",
    re.IGNORECASE,
)

_ENDPOINT_CONST_NAME_RE = re.compile(
    r"(?:^|_)(?:endpoint|issuer|url|uri)(?:_|$)",
    re.IGNORECASE,
)

_CONFIG_IDENTIFIER_NAME_RE = re.compile(
    r"(?:^|_)(?:profile_id|config_id|credential_id|token_profile_id)(?:_|$)",
    re.IGNORECASE,
)

_TEST_SECRET_VAR_PREFIX_RE = re.compile(
    r"^(?:test_|mock_|fake_|dummy_|stub_)",
    re.IGNORECASE,
)

_ENUM_BASE_NAMES: frozenset[str] = frozenset({
    "Enum",
    "StrEnum",
    "IntEnum",
    "Flag",
    "IntFlag",
    "ReprEnum",
})

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


def _normalize_secret_literal_candidate(value: str) -> str:
    """Normalize common wrapper forms around credential literals."""
    normalized = value.strip()
    lower = normalized.lower()
    for prefix in ("bearer ", "token "):
        if lower.startswith(prefix):
            return normalized[len(prefix):].lstrip()
    return normalized


def _is_endpoint_url_literal(value: str) -> bool:
    """Return True for plain HTTP(S) endpoint URL literals without credentials."""
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    # Keep detecting URLs that embed credentials (userinfo) as potential secrets.
    return parsed.username is None and parsed.password is None


def _is_file_like_literal(value: str) -> bool:
    """Return True when the literal looks like a file path/name, not a secret."""
    if not value or "\n" in value or "\r" in value:
        return False

    # Common explicit path markers.
    if value.startswith(("./", "../", "/", "~/")):
        return True
    if re.match(r"^[a-zA-Z]:\\", value):
        return True

    # A path-like segment with separators and a file extension.
    if ("/" in value or "\\" in value) and re.search(r"\.[a-zA-Z0-9]{1,8}$", value):
        return True

    # Bare file names such as ".epic_token_cache.json" or "secret.key".
    return bool(re.match(r"^\.?[A-Za-z0-9_-][A-Za-z0-9._-]*\.[A-Za-z0-9]{1,8}$", value))


def _normalize_symbol_name(name: str) -> str:
    """Normalize symbolic names so case and separators do not matter."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _expr_name(node: ast.expr) -> str | None:
    """Extract a terminal name from AST expression nodes used as class bases."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_in_enum_member_context(
    node: ast.AST,
    parent_map: dict[ast.AST, ast.AST],
) -> bool:
    """Return True when assignment is in a class body inheriting from Enum."""
    parent = parent_map.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        if isinstance(parent, ast.ClassDef):
            return any(
                (_expr_name(base) or "") in _ENUM_BASE_NAMES
                for base in parent.bases
            )
        parent = parent_map.get(parent)
    return False


def _is_symbol_declaration_literal(
    var_name: str,
    string_val: str,
    *,
    in_enum_member_context: bool,
) -> bool:
    """Suppress symbol-like literals (enum/schema constants), not credentials."""
    if not _SYMBOL_DECLARATION_RE.match(string_val):
        return False
    if in_enum_member_context:
        return True
    return _normalize_symbol_name(var_name) == _normalize_symbol_name(string_val)


def _looks_like_natural_language_message(value: str) -> bool:
    """Return True when a literal resembles a human-readable error/message text."""
    if len(value) < 20 or "\n" in value:
        return False

    words = re.findall(r"[A-Za-z]{2,}", value)
    return len(words) >= 5 and (" " in value)


def _is_ml_tokenizer_context_literal(var_name: str, string_val: str) -> bool:
    """Return True for common ML tokenizer constants that are not secrets."""
    lowered = var_name.lower()

    if lowered in _ML_TOKENIZER_SYMBOL_NAMES:
        return True

    if lowered.endswith("_token"):
        base = lowered[:-6]
        if base in _ML_TOKENIZER_BASE_NAMES:
            return True

    if lowered.endswith("_token_id"):
        base = lowered[:-9]
        if base in _ML_TOKENIZER_BASE_NAMES:
            return True

    # Chat templates and special-token literals are expected tokenizer metadata.
    if any(marker in string_val for marker in ("{{", "{%", "%}")):
        return True
    if re.match(r"^<\|?.+\|?>$", string_val):
        return True
    return bool(re.match(r"^\[[^\]]+\]$", string_val))


def _is_otel_semconv_literal(string_val: str) -> bool:
    """Return True for OpenTelemetry semantic-convention keys, not secrets."""
    if len(string_val) > 128 or " " in string_val:
        return False
    return bool(_OTEL_GENAI_SEMCONV_RE.match(string_val))


def _is_env_placeholder_template_literal(string_val: str) -> bool:
    """Return True for multi-line templates that only reference env placeholders."""
    if "\n" not in string_val and "\r" not in string_val:
        return False
    if not _ENV_PLACEHOLDER_RE.search(string_val):
        return False

    # Restrict to configuration-style templates (YAML/INI-like key-value lines).
    return ":" in string_val or "=" in string_val


def _is_env_var_name_literal(var_name: str, string_val: str) -> bool:
    """Return True when a literal stores an environment-variable NAME, not a value."""
    if not _ENV_VAR_NAME_LITERAL_RE.match(string_val):
        return False

    value_lower = string_val.lower()
    if not _SECRET_VAR_RE.search(value_lower):
        return False

    upper_name = var_name.upper()
    if upper_name.endswith(_ENV_NAME_VAR_SUFFIXES):
        return True

    return "_ENV" in upper_name


def _is_marker_constant_name(var_name: str) -> bool:
    """Return True for marker/sentinel-style constant names, not credential holders."""
    return bool(_MARKER_CONST_NAME_RE.search(var_name))


def _is_prefix_literal_candidate(value: str) -> bool:
    """Return True when a literal looks like a token prefix, not a full token."""
    stripped = value.strip()
    return len(stripped) <= 24 and stripped.endswith(("-", "_"))


def _is_endpoint_template_literal(var_name: str, string_val: str) -> bool:
    """Return True for endpoint/issuer constants composed as templates."""
    if not _ENDPOINT_CONST_NAME_RE.search(var_name):
        return False
    if "${" in string_val and "/" in string_val:
        return True
    return _is_endpoint_url_literal(string_val)


def _is_config_identifier_literal(var_name: str, string_val: str) -> bool:
    """Return True for profile/config identifier constants, not secrets."""
    if not _CONFIG_IDENTIFIER_NAME_RE.search(var_name):
        return False
    if " " in string_val:
        return False
    return bool(re.match(r"^[a-z0-9][a-z0-9:_-]{3,}$", string_val, flags=re.IGNORECASE))


def _is_test_fixture_like_path(file_path: Path) -> bool:
    """Return True for test-fixture style paths not covered by generic test detection."""
    value = file_path.as_posix().lower()
    return (
        "test-fixture" in value
        or "test_fixture" in value
        or ".test-helpers." in value
        or ".test_helpers." in value
    )


def _is_test_prefixed_secret_var(var_name: str) -> bool:
    """Return True for test-fixture constant prefixes that should not trigger HSC."""
    return bool(_TEST_SECRET_VAR_PREFIX_RE.match(var_name))


def _is_dynamic_template_literal(quote: str, string_val: str) -> bool:
    """Return True for JS/TS template literals that interpolate runtime values."""
    return quote == "`" and "${" in string_val


@register_signal
class HardcodedSecretSignal(BaseSignal):
    """Detect hardcoded secrets and credentials in source code."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.HARDCODED_SECRET

    @property
    def name(self) -> str:
        return "Hardcoded Secret"

    _TS_LANGS = frozenset({"typescript", "tsx", "javascript", "jsx"})

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
            if is_test_file(pr.file_path) or _is_test_fixture_like_path(pr.file_path):
                continue

            if pr.language == "python":
                findings.extend(
                    self._analyze_python(pr, min_entropy, min_length)
                )
            elif pr.language in self._TS_LANGS:
                findings.extend(
                    self._analyze_typescript(pr, min_entropy, min_length)
                )

        return findings

    # ------------------------------------------------------------------
    # Python analysis (AST-based)
    # ------------------------------------------------------------------

    def _analyze_python(
        self,
        pr: ParseResult,
        min_entropy: float,
        min_length: int,
    ) -> list[Finding]:
        findings: list[Finding] = []
        try:
            repo_path = self._repo_path or Path(".")
            source = (repo_path / pr.file_path).read_text(
                encoding="utf-8", errors="replace"
            )
            tree = ast.parse(source, filename=str(pr.file_path))
        except (SyntaxError, OSError):
            return findings

        parent_map = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        for node in ast.walk(tree):
            finding = self._check_assignment(
                node, pr.file_path, min_entropy, min_length, parent_map
            )
            if finding:
                findings.append(finding)

        return findings

    # ------------------------------------------------------------------
    # TypeScript / JavaScript analysis (tree-sitter)
    # ------------------------------------------------------------------

    def _analyze_typescript(
        self,
        pr: ParseResult,
        min_entropy: float,
        min_length: int,
    ) -> list[Finding]:
        """Detect hardcoded secrets in TS/JS files via tree-sitter."""
        findings: list[Finding] = []
        repo_path = self._repo_path or Path(".")
        try:
            source = (repo_path / pr.file_path).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return findings

        # Regex-based line-level scan (language-neutral heuristics).
        # Matches: const SECRET = "value", let apiKey = 'value', export const TOKEN = `value`
        var_assign_re = re.compile(
            r"""^[ \t]*(?:export\s+)?(?:const|let|var)\s+"""
            r"""([A-Za-z_$][A-Za-z0-9_$]*)\s*"""
            r"""(?::\s*\S+?\s*)?=\s*"""
            r"""(['"`])(.+?)\2""",
        )
        for lineno, line in enumerate(source.splitlines(), start=1):
            m = var_assign_re.match(line)
            if not m:
                continue
            var_name, _quote, string_val = m.group(1), m.group(2), m.group(3)

            finding = self._evaluate_ts_assignment(
                var_name, _quote, string_val, pr.file_path, lineno,
                min_entropy, min_length, line,
            )
            if finding:
                findings.append(finding)

        return findings

    def _evaluate_ts_assignment(
        self,
        var_name: str,
        quote: str,
        string_val: str,
        file_path: Path,
        lineno: int,
        min_entropy: float,
        min_length: int,
        line_text: str,
    ) -> Finding | None:
        """Evaluate a TS/JS variable assignment for secret patterns."""
        # Safe patterns: process.env.*, require("dotenv"), etc.
        if "process.env" in line_text or "import.meta.env" in line_text:
            return None

        if _is_test_prefixed_secret_var(var_name):
            return None

        if _is_dynamic_template_literal(quote, string_val):
            return None

        # Check known API token prefixes first (high confidence).
        candidate = _normalize_secret_literal_candidate(string_val)
        for prefix in _KNOWN_PREFIXES:
            if candidate.startswith(prefix):
                if _is_marker_constant_name(var_name) and _is_prefix_literal_candidate(candidate):
                    continue
                return self._make_finding(
                    var_name, file_path, lineno,
                    rule_id="hardcoded_api_token",
                    score=0.9,
                    detail=f"Value starts with known API token prefix '{prefix}'.",
                )

        # Variable-name-based detection.
        if not _SECRET_VAR_RE.search(var_name):
            return None

        if len(string_val) < 8:
            return None

        # Suppression heuristics (shared with Python).
        if _PLACEHOLDER_RE.match(string_val):
            return self._make_finding(
                var_name, file_path, lineno,
                rule_id="placeholder_secret",
                score=0.5,
                detail=(
                    "Placeholder secret detected. Replace with a proper "
                    "secret before deployment."
                ),
            )

        if _is_endpoint_url_literal(string_val):
            return None
        if _is_endpoint_template_literal(var_name, string_val):
            return None
        if _is_env_var_name_literal(var_name, string_val):
            return None
        if _is_config_identifier_literal(var_name, string_val):
            return None
        if _is_marker_constant_name(var_name):
            return None
        if _is_file_like_literal(string_val):
            return None
        if _is_ml_tokenizer_context_literal(var_name, string_val):
            return None
        if _is_otel_semconv_literal(string_val):
            return None
        if _is_env_placeholder_template_literal(string_val):
            return None
        if _looks_like_natural_language_message(string_val):
            return None

        # Entropy-based detection.
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

        if len(string_val) >= min_length:
            return self._make_finding(
                var_name, file_path, lineno,
                rule_id="hardcoded_secret",
                score=0.6,
                detail="String literal assigned to security-sensitive variable.",
            )

        return None

    def _check_assignment(
        self,
        node: ast.AST,
        file_path: Path,
        min_entropy: float,
        min_length: int,
        parent_map: dict[ast.AST, ast.AST],
    ) -> Finding | None:
        """Check a single AST node for hardcoded secret patterns."""
        # Handle: NAME = "value"
        if isinstance(node, ast.Assign):
            in_enum_member_context = _is_in_enum_member_context(node, parent_map)
            for target in node.targets:
                var_name = self._extract_var_name(target)
                if not var_name:
                    continue

                # High-confidence token prefixes should fire even for generic
                # variable names (for example CONFIG_VALUE = "ghp_...").
                known_prefix_finding = self._detect_known_prefix_literal(
                    node.value, var_name, file_path, node.lineno
                )
                if known_prefix_finding:
                    return known_prefix_finding

                if _SECRET_VAR_RE.search(var_name):
                    return self._evaluate_value(
                        node.value, var_name, file_path, node.lineno,
                        min_entropy, min_length,
                        in_enum_member_context=in_enum_member_context,
                    )

        # Handle: NAME: type = "value"
        if isinstance(node, ast.AnnAssign) and node.value and node.target:
            in_enum_member_context = _is_in_enum_member_context(node, parent_map)
            var_name = self._extract_var_name(node.target)
            if not var_name:
                return None

            known_prefix_finding = self._detect_known_prefix_literal(
                node.value, var_name, file_path, node.lineno
            )
            if known_prefix_finding:
                return known_prefix_finding

            if _SECRET_VAR_RE.search(var_name):
                return self._evaluate_value(
                    node.value, var_name, file_path, node.lineno,
                    min_entropy, min_length,
                    in_enum_member_context=in_enum_member_context,
                )

        # Handle keyword arguments: func(secret_key="value")
        if isinstance(node, ast.keyword) and node.arg:
            known_prefix_finding = self._detect_known_prefix_literal(
                node.value,
                node.arg,
                file_path,
                getattr(node, "lineno", 0),
            )
            if known_prefix_finding:
                return known_prefix_finding

            if _SECRET_VAR_RE.search(node.arg):
                return self._evaluate_value(
                    node.value, node.arg, file_path,
                    getattr(node, "lineno", 0),
                    min_entropy, min_length,
                    in_enum_member_context=False,
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

    def _detect_known_prefix_literal(
        self,
        value_node: ast.expr,
        var_name: str,
        file_path: Path,
        lineno: int,
    ) -> Finding | None:
        """Detect high-confidence known secret prefixes irrespective of variable name."""
        if _is_safe_value(value_node):
            return None

        if _is_test_prefixed_secret_var(var_name):
            return None

        string_val = _extract_string_value(value_node)
        if string_val is None or len(string_val) < 8:
            return None

        candidate = _normalize_secret_literal_candidate(string_val)

        for prefix in _KNOWN_PREFIXES:
            if candidate.startswith(prefix):
                if _is_marker_constant_name(var_name) and _is_prefix_literal_candidate(candidate):
                    continue
                return self._make_finding(
                    var_name,
                    file_path,
                    lineno,
                    rule_id="hardcoded_api_token",
                    score=0.9,
                    detail=f"Value starts with known API token prefix '{prefix}'.",
                )

        return None

    def _evaluate_value(
        self,
        value_node: ast.expr,
        var_name: str,
        file_path: Path,
        lineno: int,
        min_entropy: float,
        min_length: int,
        *,
        in_enum_member_context: bool,
    ) -> Finding | None:
        """Evaluate whether the assigned value is a hardcoded secret."""
        if _is_safe_value(value_node):
            return None

        if _is_test_prefixed_secret_var(var_name):
            return None

        string_val = _extract_string_value(value_node)
        if string_val is None:
            return None

        # Skip empty / very short strings.
        if len(string_val) < 8:
            return None

        # Check for known API token prefixes (high confidence).
        normalized_literal = _normalize_secret_literal_candidate(string_val)
        for prefix in _KNOWN_PREFIXES:
            if normalized_literal.startswith(prefix):
                if (
                    _is_marker_constant_name(var_name)
                    and _is_prefix_literal_candidate(normalized_literal)
                ):
                    continue
                return self._make_finding(
                    var_name, file_path, lineno,
                    rule_id="hardcoded_api_token",
                    score=0.9,
                    detail=f"Value starts with known API token prefix '{prefix}'.",
                )

        # OAuth/auth endpoint constants (for example TOKEN_URL/AUTH_URL) are
        # common and are not credentials by themselves.
        if _is_endpoint_url_literal(string_val):
            return None
        if _is_endpoint_template_literal(var_name, string_val):
            return None

        # Constants such as API_KEY_ENV = "OPENAI_API_KEY" describe env-var
        # names, not hardcoded credential material.
        if _is_env_var_name_literal(var_name, string_val):
            return None

        # Sentinel/marker constants (for example *_TOKEN_PREFIX, *_ERROR_CODE)
        # are often operational metadata rather than credentials.
        if _is_marker_constant_name(var_name):
            return None

        if _is_config_identifier_literal(var_name, string_val):
            return None

        # Filename/path constants can contain "token"/"secret" in their symbol
        # names but the literal itself is usually operational metadata.
        if _is_file_like_literal(string_val):
            return None

        # Enum/schema declaration symbols are often secret-shaped names, not secrets.
        if _is_symbol_declaration_literal(
            var_name,
            string_val,
            in_enum_member_context=in_enum_member_context,
        ):
            return None

        # Human-readable error/warning/message constants are commonly named with
        # secret-like tokens (for example MAX_TOKENS_ERROR) but are not credentials.
        if _MESSAGE_SUFFIX_RE.search(var_name) and _looks_like_natural_language_message(
            string_val
        ):
            return None

        # ML tokenizer metadata (pad_token/chat_template/tokenizer_class_name)
        # uses "token" as NLP terminology, not credential material.
        if _is_ml_tokenizer_context_literal(var_name, string_val):
            return None

        # OpenTelemetry semantic-convention constants are telemetry metadata,
        # not credential material (for example gen_ai.usage.input_tokens).
        if _is_otel_semconv_literal(string_val):
            return None

        # Config templates can mention env vars like ${OPENAI_API_KEY} while
        # still not containing any hardcoded credential value.
        if _is_env_placeholder_template_literal(string_val):
            return None

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
        finding_context = classify_file_context(file_path)
        effective_score = score
        if finding_context == "test":
            effective_score *= 0.5

        severity = Severity.HIGH if effective_score >= 0.6 else Severity.MEDIUM
        return Finding(
            signal_type=self.signal_type,
            severity=severity,
            score=effective_score,
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
                "finding_context": finding_context,
            },
            rule_id=rule_id,
            finding_context=finding_context,
        )
