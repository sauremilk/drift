"""Tests for Hardcoded Secret signal (HSC)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    ParseResult,
    SignalType,
)
from drift.signals.hardcoded_secret import (
    HardcodedSecretSignal,
    _shannon_entropy,
)


def _make_pr(file_path: str = "config.py") -> ParseResult:
    return ParseResult(
        file_path=Path(file_path),
        language="python",
    )


def _write_source(tmp_path: Path, rel_path: str, code: str) -> None:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(textwrap.dedent(code), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit: entropy calculation
# ---------------------------------------------------------------------------


class TestShannonEntropy:
    def test_empty_string(self) -> None:
        assert _shannon_entropy("") == 0.0

    def test_single_char(self) -> None:
        assert _shannon_entropy("aaaa") == 0.0

    def test_high_entropy(self) -> None:
        # Random-looking string should have high entropy
        val = "aB3$xZ9!kL2@mN5#"
        assert _shannon_entropy(val) > 3.5

    def test_low_entropy(self) -> None:
        assert _shannon_entropy("aaabbbccc") < 2.0


# ---------------------------------------------------------------------------
# True positives: should detect hardcoded secrets
# ---------------------------------------------------------------------------


class TestHSCTruePositives:
    def test_secret_key_hardcoded(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "settings.py",
            '''\
            SECRET_KEY = "s3cr3t-k3y-th4t-1s-v3ry-l0ng-4nd-r4nd0m"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("settings.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.HARDCODED_SECRET
        assert "SECRET_KEY" in findings[0].title

    def test_github_token(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_aws_access_key(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            access_key = "AKIAIOSFODNN7EXAMPLE"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_openai_key(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"

    def test_password_literal(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            db_password = "SuperSecretPassword123!"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert "db_password" in findings[0].title

    def test_token_url_with_embedded_credentials_still_detected(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            TOKEN_URL = "https://user:supersecret@example.com/oauth/token"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert "TOKEN_URL" in findings[0].title

    def test_placeholder_secret(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = "your-secret-here"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1

    def test_annotated_assignment(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            api_token: str = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1

    def test_enum_member_with_real_token_still_detected(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            from enum import Enum

            class CredentialExample(Enum):
                API_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"


# ---------------------------------------------------------------------------
# True negatives: should NOT flag these
# ---------------------------------------------------------------------------


class TestHSCTrueNegatives:
    def test_env_variable(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            import os
            SECRET_KEY = os.environ["SECRET_KEY"]
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_getenv(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            import os
            SECRET_KEY = os.getenv("SECRET_KEY", "fallback")
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_config_get(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = config.get("secret_key")
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_short_string(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            secret = "short"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_test_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "tests/test_auth.py",
            '''\
            SECRET_KEY = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("tests/test_auth.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_python_skipped(self, tmp_path: Path) -> None:
        pr = ParseResult(file_path=Path("config.ts"), language="typescript")
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([pr], {}, DriftConfig())
        assert len(findings) == 0

    def test_non_secret_variable(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            APP_NAME = "my-really-great-production-application"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_fstring_value(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            env = "prod"
            secret_key = f"prefix-{env}-suffix-dynamic"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_enum_symbolic_member_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            from enum import Enum

            class SecretFields(Enum):
                API_TOKEN = "api_token"
                CLIENT_SECRET = "client_secret"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_schema_symbolic_constant_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            class ApiSchema:
                SECRET_KEY = "secret_key"
                API_TOKEN = "apiToken"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0

    def test_token_url_oauth_endpoint_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "oauth.py",
            '''\
            TOKEN_URL = "https://oauth2.googleapis.com/token"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("oauth.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_auth_url_oauth_endpoint_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "oauth.py",
            '''\
            AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("oauth.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_token_cache_file_constant_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "constants.py",
            '''\
            TOKEN_CACHE_FILE = ".epic_token_cache.json"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("constants.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_error_message_constant_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "openai_tools.py",
            '''\
            _MAX_TOKENS_ERROR = (
                "Output parser received a `max_tokens` stop reason. "
                "The output is likely incomplete please increase `max_tokens` "
                "or shorten your prompt."
            )
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("openai_tools.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_ml_tokenizer_tokens_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "tokenizer_config.py",
            '''\
            pad_token = "<|pad|>"
            cls_token = "[CLS]"
            eos_token = "</s>"
            bos_token = "<s>"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("tokenizer_config.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_ml_tokenizer_class_and_template_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "tokenization_llm.py",
            '''\
            tokenizer_class = "LlamaTokenizer"
            tokenizer_class_name = "LlamaTokenizerFast"
            chat_template = "{{ bos_token }}{% for m in messages %}{{ m['content'] }}{% endfor %}"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("tokenization_llm.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_ml_vocab_files_names_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "tokenization_vocab.py",
            '''\
            vocab_files_names = {
                "vocab_file": "vocab.txt",
                "tokenizer_file": "tokenizer.json",
            }
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("tokenization_vocab.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_ml_tokenizer_keyword_arg_not_flagged(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "build_tokenizer.py",
            '''\
            def build_tokenizer(factory):
                return factory(pad_token="<|pad|>", sep_token="[SEP]")
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("build_tokenizer.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_ml_tokenizer_name_does_not_suppress_real_prefix_secret(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path,
            "tokenizer_secrets.py",
            '''\
            pad_token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("tokenizer_secrets.py")], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].rule_id == "hardcoded_api_token"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestHSCEdgeCases:
    def test_metadata_includes_cwe(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 1
        assert findings[0].metadata["cwe"] == "CWE-798"

    def test_fix_suggestion_present(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            SECRET_KEY = "s3cr3t-v3ry-l0ng-k3y-f0r-pr0d"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].fix is not None
        assert "os.environ" in findings[0].fix

    def test_empty_parse_results(self, tmp_path: Path) -> None:
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([], {}, DriftConfig())
        assert len(findings) == 0

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "broken.py",
            '''\
            SECRET_KEY = "ghp_test" def broken
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        pr = _make_pr("broken.py")
        findings = signal.analyze([pr], {}, DriftConfig())
        # Should not crash, may or may not find the secret depending on parse
        assert isinstance(findings, list)

    def test_class_attribute_secret(self, tmp_path: Path) -> None:
        _write_source(
            tmp_path, "config.py",
            '''\
            class Config:
                secret_key = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Multi-line secrets
# ---------------------------------------------------------------------------


class TestMultilineSecrets:
    def test_pem_private_key_detected(self, tmp_path: Path) -> None:
        # Triple-quoted PEM key — common in config files and CI scripts
        _write_source(
            tmp_path, "config.py",
            '''\
            private_key = """-----BEGIN RSA PRIVATE KEY-----
            MIIEowIBAAKCAQEA2a2rwplBQLzHPZe5RJaItBWFkMVaVEFVCpkJuGZCqqDSX/s6
            bMECBEmzKFBMFZGQfJ7sM3N4zGAVDGRMkHVFHfCkBjIRzLv0bKTjQ8IkK1l2mPFN
            y3qXCPZGhJqJVJuZiKxjM5TbLBLpC1J4JFHxlXJzKVZiT6ygGdLK5oaVZdPxLvWm
            -----END RSA PRIVATE KEY-----"""
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.HARDCODED_SECRET
        assert "private_key" in findings[0].title

    def test_base64_token_block_detected(self, tmp_path: Path) -> None:
        # Multi-line triple-quoted base64 token — high entropy, long string
        _write_source(
            tmp_path, "config.py",
            '''\
            api_key = """
            dGhpcyBpcyBhIHZlcnkgbG9uZyBiYXNlNjQgZW5jb2RlZCB0b2tlbiB0aGF0
            c2hvdWxkIGJlIGRldGVjdGVkIGJ5IHRoZSBoYXJkY29kZWQgc2VjcmV0IHNpZ25hbA==
            """
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert "api_key" in findings[0].title

    def test_multiline_connection_string_with_password_detected(
        self, tmp_path: Path
    ) -> None:
        # Implicit string concatenation — joined into one constant by Python
        _write_source(
            tmp_path, "config.py",
            '''\
            db_password = (
                "postgresql://admin:S3cr3tP@ssw0rd123!"
                "@prod-db.internal:5432/appdb"
            )
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) >= 1
        assert "db_password" in findings[0].title

    def test_multiline_sql_query_not_flagged(self, tmp_path: Path) -> None:
        # Non-secret variable name — should never trigger regardless of length
        _write_source(
            tmp_path, "queries.py",
            '''\
            sql_query = """
                SELECT id, name, email
                FROM users
                WHERE active = true
                AND created_at > '2024-01-01'
            """
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr("queries.py")], {}, DriftConfig())
        assert len(findings) == 0

    def test_multiline_help_text_not_flagged(self, tmp_path: Path) -> None:
        # Long descriptive string mentioning "secret" only as a word, not a var name
        _write_source(
            tmp_path, "config.py",
            '''\
            HELP_TEXT = """
                This application requires the following environment variables:
                - SECRET_KEY: set this to a random value before deploying
                - DATABASE_URL: connection string for the primary database
                - REDIS_URL: connection string for the cache layer
            """
            ''',
        )
        signal = HardcodedSecretSignal(repo_path=tmp_path)
        findings = signal.analyze([_make_pr()], {}, DriftConfig())
        assert len(findings) == 0
