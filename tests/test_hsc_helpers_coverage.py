"""Coverage tests for hardcoded_secret pure helpers:
_is_safe_value, _extract_string_value, _normalize_secret_literal_candidate,
_is_endpoint_url_literal, _is_file_like_literal, _normalize_symbol_name,
_expr_name, _is_in_enum_member_context, _is_symbol_declaration_literal,
_looks_like_natural_language_message, _is_ml_tokenizer_context_literal,
_is_otel_semconv_literal, _is_env_placeholder_template_literal."""

from __future__ import annotations

import ast

from drift.signals.hardcoded_secret import (
    _expr_name,
    _extract_string_value,
    _is_endpoint_url_literal,
    _is_env_placeholder_template_literal,
    _is_env_var_name_literal,
    _is_file_like_literal,
    _is_in_enum_member_context,
    _is_marker_constant_name,
    _is_ml_tokenizer_context_literal,
    _is_otel_semconv_literal,
    _is_safe_value,
    _is_symbol_declaration_literal,
    _looks_like_natural_language_message,
    _normalize_secret_literal_candidate,
    _normalize_symbol_name,
)

# -- _is_safe_value ------------------------------------------------------------


class TestIsSafeValue:
    def test_getenv_call(self):
        node = ast.parse("os.getenv('KEY')").body[0].value  # type: ignore[attr-defined]
        assert _is_safe_value(node) is True

    def test_config_call(self):
        node = ast.parse("Config('key')").body[0].value  # type: ignore[attr-defined]
        assert _is_safe_value(node) is True

    def test_environ_subscript(self):
        node = ast.parse("os.environ['KEY']").body[0].value  # type: ignore[attr-defined]
        assert _is_safe_value(node) is True

    def test_fstring(self):
        node = ast.parse("f'{prefix}_secret'").body[0].value  # type: ignore[attr-defined]
        assert _is_safe_value(node) is True

    def test_string_literal(self):
        node = ast.parse("'hard_coded'").body[0].value  # type: ignore[attr-defined]
        assert _is_safe_value(node) is False


# -- _extract_string_value -----------------------------------------------------


class TestExtractStringValue:
    def test_str_constant(self):
        node = ast.parse("'hello'").body[0].value  # type: ignore[attr-defined]
        assert _extract_string_value(node) == "hello"

    def test_int_constant(self):
        node = ast.parse("42").body[0].value  # type: ignore[attr-defined]
        assert _extract_string_value(node) is None

    def test_name_node(self):
        node = ast.parse("x").body[0].value  # type: ignore[attr-defined]
        assert _extract_string_value(node) is None


# -- _normalize_secret_literal_candidate ----------------------------------------


class TestNormalizeSecretLiteralCandidate:
    def test_bearer_prefix(self):
        assert _normalize_secret_literal_candidate("Bearer abc123") == "abc123"

    def test_token_prefix(self):
        assert _normalize_secret_literal_candidate("token xyz") == "xyz"

    def test_no_prefix(self):
        assert _normalize_secret_literal_candidate("abc123") == "abc123"

    def test_whitespace_stripped(self):
        assert _normalize_secret_literal_candidate("  abc  ") == "abc"


# -- _is_endpoint_url_literal --------------------------------------------------


class TestIsEndpointUrlLiteral:
    def test_plain_http(self):
        assert _is_endpoint_url_literal("http://api.example.com/v1") is True

    def test_https(self):
        assert _is_endpoint_url_literal("https://api.example.com") is True

    def test_url_with_userinfo(self):
        assert _is_endpoint_url_literal("https://user:pass@host.com") is False  # noqa: E501  # pragma: allowlist secret

    def test_not_http(self):
        assert _is_endpoint_url_literal("ftp://server/file") is False

    def test_no_scheme(self):
        assert _is_endpoint_url_literal("just-a-string") is False


# -- _is_file_like_literal -----------------------------------------------------


class TestIsFileLikeLiteral:
    def test_relative_path(self):
        assert _is_file_like_literal("./config.json") is True

    def test_windows_path(self):
        assert _is_file_like_literal("C:\\secrets.txt") is True

    def test_unix_absolute(self):
        assert _is_file_like_literal("/etc/config.yaml") is True

    def test_home_relative(self):
        assert _is_file_like_literal("~/config.toml") is True

    def test_bare_filename(self):
        assert _is_file_like_literal("secret.key") is True

    def test_dotfile(self):
        assert _is_file_like_literal(".epic_token_cache.json") is True

    def test_empty_string(self):
        assert _is_file_like_literal("") is False

    def test_newline_in_value(self):
        assert _is_file_like_literal("line1\nline2") is False

    def test_path_with_separator_and_ext(self):
        assert _is_file_like_literal("foo/bar/baz.txt") is True


# -- _normalize_symbol_name ---------------------------------------------------


class TestNormalizeSymbolName:
    def test_uppercase(self):
        assert _normalize_symbol_name("SECRET_KEY") == "secretkey"

    def test_camel_case(self):
        assert _normalize_symbol_name("SecretKey") == "secretkey"

    def test_special_chars(self):
        assert _normalize_symbol_name("secret-key:v2") == "secretkeyv2"


# -- _expr_name ---------------------------------------------------------------


class TestExprName:
    def test_name_node(self):
        node = ast.parse("Enum").body[0].value  # type: ignore[attr-defined]
        assert _expr_name(node) == "Enum"

    def test_attribute_node(self):
        node = ast.parse("enum.StrEnum").body[0].value  # type: ignore[attr-defined]
        assert _expr_name(node) == "StrEnum"

    def test_other_node(self):
        node = ast.parse("42").body[0].value  # type: ignore[attr-defined]
        assert _expr_name(node) is None


# -- _is_in_enum_member_context ------------------------------------------------


class TestIsInEnumMemberContext:
    def _build_parent_map(self, tree: ast.AST) -> dict[ast.AST, ast.AST]:
        m: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                m[child] = parent
        return m

    def test_enum_class(self):
        src = "class Color(Enum):\n    RED = 'red'"
        tree = ast.parse(src)
        pmap = self._build_parent_map(tree)
        assign = tree.body[0].body[0]  # type: ignore[attr-defined]
        assert _is_in_enum_member_context(assign, pmap) is True

    def test_non_enum_class(self):
        src = "class Foo:\n    X = 'y'"
        tree = ast.parse(src)
        pmap = self._build_parent_map(tree)
        assign = tree.body[0].body[0]  # type: ignore[attr-defined]
        assert _is_in_enum_member_context(assign, pmap) is False

    def test_function_inside_class(self):
        src = "class Color(Enum):\n    def setup(self):\n        x = 'y'"
        tree = ast.parse(src)
        pmap = self._build_parent_map(tree)
        assign = tree.body[0].body[0].body[0]  # type: ignore[attr-defined]
        assert _is_in_enum_member_context(assign, pmap) is False


# -- _is_symbol_declaration_literal --------------------------------------------


class TestIsSymbolDeclarationLiteral:
    def test_enum_context(self):
        assert _is_symbol_declaration_literal("FOO", "FOO", in_enum_member_context=True) is True

    def test_name_matches_value(self):
        assert (
            _is_symbol_declaration_literal("SECRET_KEY", "secret-key", in_enum_member_context=False)
            is True
        )

    def test_no_match(self):
        assert (
            _is_symbol_declaration_literal("API_KEY", "ghp_abc123xyz", in_enum_member_context=False)
            is False
        )

    def test_non_symbol_value(self):
        # Value doesn't match symbol regex
        assert (
            _is_symbol_declaration_literal("X", "hello world", in_enum_member_context=True) is False
        )


# -- _looks_like_natural_language_message --------------------------------------


class TestLooksLikeNaturalLanguageMessage:
    def test_long_sentence(self):
        assert (
            _looks_like_natural_language_message("This is a multi word sentence with many tokens")
            is True
        )

    def test_short_string(self):
        assert _looks_like_natural_language_message("short") is False

    def test_newline(self):
        assert _looks_like_natural_language_message("line one\nline two") is False

    def test_no_spaces(self):
        assert _looks_like_natural_language_message("abcdefghijklmnopqrstuvwxyz") is False


# -- _is_ml_tokenizer_context_literal ------------------------------------------


class TestIsMlTokenizerContextLiteral:
    def test_chat_template(self):
        assert _is_ml_tokenizer_context_literal("chat_template", "{{message}}") is True

    def test_pad_token(self):
        assert _is_ml_tokenizer_context_literal("pad_token", "[PAD]") is True

    def test_pad_token_id(self):
        assert _is_ml_tokenizer_context_literal("pad_token_id", "0") is True

    def test_special_token_marker(self):
        assert _is_ml_tokenizer_context_literal("x", "<|endoftext|>") is True

    def test_bracket_pattern(self):
        assert _is_ml_tokenizer_context_literal("x", "[MASK]") is True

    def test_jinja_template(self):
        assert _is_ml_tokenizer_context_literal("x", "{% for m in messages %}") is True

    def test_unrelated(self):
        assert _is_ml_tokenizer_context_literal("api_key", "ghp_abc") is False

    def test_tokenizer_class_name(self):
        assert _is_ml_tokenizer_context_literal("tokenizer_class", "GPT2Tokenizer") is True


# -- _is_otel_semconv_literal --------------------------------------------------


class TestIsOtelSemconvLiteral:
    def test_valid(self):
        assert _is_otel_semconv_literal("gen_ai.system.message") is True

    def test_too_long(self):
        assert _is_otel_semconv_literal("gen_ai." + "x" * 200) is False

    def test_has_space(self):
        assert _is_otel_semconv_literal("gen ai.system") is False

    def test_no_match(self):
        assert _is_otel_semconv_literal("just_a_name") is False


# -- _is_env_placeholder_template_literal --------------------------------------


class TestIsEnvPlaceholderTemplateLiteral:
    def test_yaml_template(self):
        val = "host: ${DB_HOST}\nport: ${DB_PORT}"
        assert _is_env_placeholder_template_literal(val) is True

    def test_single_line(self):
        assert _is_env_placeholder_template_literal("${VAR}") is False

    def test_multiline_no_placeholder(self):
        assert _is_env_placeholder_template_literal("line1\nline2") is False

    def test_ini_template(self):
        val = "key = ${SECRET}\nother = ${TOKEN}"
        assert _is_env_placeholder_template_literal(val) is True


# -- _is_env_var_name_literal ---------------------------------------------------


class TestIsEnvVarNameLiteral:
    def test_env_suffix_detected(self):
        assert _is_env_var_name_literal("AWS_SECRET_KEY_ENV", "AWS_SECRET_ACCESS_KEY") is True

    def test_var_suffix_detected(self):
        assert _is_env_var_name_literal("OPENAI_API_KEY_VAR", "OPENAI_API_KEY") is True

    def test_not_all_caps_value(self):
        assert _is_env_var_name_literal("API_KEY_ENV", "openai_api_key") is False

    def test_not_secret_shaped_value(self):
        assert _is_env_var_name_literal("AUTH_ENV", "APP_SETTINGS") is False


# -- _is_marker_constant_name ---------------------------------------------------


class TestIsMarkerConstantName:
    def test_marker(self):
        assert _is_marker_constant_name("GCP_VERTEX_CREDENTIALS_MARKER") is True

    def test_prefix(self):
        assert _is_marker_constant_name("ANTHROPIC_SETUP_TOKEN_PREFIX") is True

    def test_message(self):
        assert _is_marker_constant_name("DEVICE_TOKEN_ROTATION_DENIED_MESSAGE") is True

    def test_error_code(self):
        assert _is_marker_constant_name("GATEWAY_SECRET_REF_UNAVAILABLE_ERROR_CODE") is True

    def test_regular_secret_name(self):
        assert _is_marker_constant_name("OPENAI_API_KEY") is False
