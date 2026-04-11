"""Coverage tests for doc_impl_drift helpers:
_strip_urls, _has_directory_context, _extract_contextual_dir_refs,
_collect_sibling_text, _is_noise_dir_reference, _is_likely_proper_noun,
_is_version_or_numeric_segment."""

from __future__ import annotations

from drift.signals.doc_impl_drift import (
    _collect_sibling_text,
    _extract_contextual_dir_refs,
    _has_directory_context,
    _is_likely_proper_noun,
    _is_noise_dir_reference,
    _is_version_or_numeric_segment,
    _strip_urls,
)

# -- _strip_urls ---------------------------------------------------------------


class TestStripUrls:
    def test_removes_http(self):
        assert _strip_urls("see http://example.com for details") == "see  for details"

    def test_removes_https(self):
        assert _strip_urls("https://github.com/org/repo") == ""

    def test_no_url(self):
        assert _strip_urls("plain text") == "plain text"

    def test_multiple_urls(self):
        result = _strip_urls("go to http://a.com and https://b.com ok")
        assert "http" not in result
        assert "ok" in result


# -- _has_directory_context ----------------------------------------------------


class TestHasDirectoryContext:
    def test_keyword_near(self):
        text = "The directory layout includes src/foo/"
        # "directory" is within 48 chars of "src/foo/"
        start = text.index("src/foo/")
        end = start + len("src/foo/")
        assert _has_directory_context(text, start, end) is True

    def test_keyword_far_away(self):
        text = "directory " + "x" * 100 + " src/foo/"
        start = text.index("src/foo/")
        end = start + len("src/foo/")
        assert _has_directory_context(text, start, end) is False

    def test_no_keyword(self):
        text = "something src/foo/ here"
        start = text.index("src/foo/")
        end = start + len("src/foo/")
        assert _has_directory_context(text, start, end) is False


# -- _extract_contextual_dir_refs ----------------------------------------------


class TestExtractContextualDirRefs:
    def test_backtick_wrapped(self):
        refs = _extract_contextual_dir_refs("The directory structure uses `src/drift/` for code")
        assert any("drift" in r for r in refs)

    def test_allow_without_context(self):
        refs = _extract_contextual_dir_refs("src/pkg/ is important", allow_without_context=True)
        assert len(refs) > 0

    def test_no_refs(self):
        refs = _extract_contextual_dir_refs("plain text no paths")
        assert len(refs) == 0

    def test_url_stripped(self):
        # URLs should be stripped before extraction
        refs = _extract_contextual_dir_refs(
            "see https://github.com/org/repo/tree/main/src for info"
        )
        # Should NOT extract URL path segments like "org", "repo", "tree"
        for r in refs:
            assert "github" not in r


# -- _collect_sibling_text -----------------------------------------------------


class TestCollectSiblingText:
    def test_text_nodes(self):
        children = [
            {"type": "text", "raw": "hello"},
            {"type": "text", "raw": "world"},
        ]
        assert _collect_sibling_text(children) == "hello world"

    def test_softbreak(self):
        children = [
            {"type": "text", "raw": "a"},
            {"type": "softbreak", "raw": "\n"},
            {"type": "text", "raw": "b"},
        ]
        result = _collect_sibling_text(children)
        assert "a" in result and "b" in result

    def test_non_text_skipped(self):
        children = [
            {"type": "image", "raw": "img.png"},
            {"type": "text", "raw": "caption"},
        ]
        assert _collect_sibling_text(children) == "caption"

    def test_empty(self):
        assert _collect_sibling_text([]) == ""


# -- _is_noise_dir_reference ---------------------------------------------------


class TestIsNoiseDirReference:
    def test_short_name(self):
        assert _is_noise_dir_reference("ab") is True

    def test_proper_noun(self):
        assert _is_noise_dir_reference("GitHub") is True

    def test_version_segment(self):
        assert _is_noise_dir_reference("v1.2") is True

    def test_valid_dir(self):
        assert _is_noise_dir_reference("src") is False


# -- _is_likely_proper_noun ----------------------------------------------------


class TestIsLikelyProperNoun:
    def test_capitalized(self):
        assert _is_likely_proper_noun("Docker") is True

    def test_all_upper(self):
        assert _is_likely_proper_noun("README") is False

    def test_lowercase(self):
        assert _is_likely_proper_noun("docker") is False

    def test_underscore(self):
        assert _is_likely_proper_noun("My_Thing") is False

    def test_with_digit(self):
        assert _is_likely_proper_noun("Token2") is False

    def test_empty(self):
        assert _is_likely_proper_noun("") is False


# -- _is_version_or_numeric_segment -------------------------------------------


class TestIsVersionOrNumericSegment:
    def test_version(self):
        assert _is_version_or_numeric_segment("v1.2.3") is True

    def test_year(self):
        assert _is_version_or_numeric_segment("2024") is True

    def test_short_number(self):
        assert _is_version_or_numeric_segment("42") is False

    def test_empty(self):
        assert _is_version_or_numeric_segment("") is False

    def test_text(self):
        assert _is_version_or_numeric_segment("src") is False
