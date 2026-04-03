"""Tests for the enhanced DIA (Markdown-AST + URL-filter)."""

from __future__ import annotations

from drift.signals.doc_impl_drift import (
    _extract_dir_refs_from_ast,
    _is_likely_proper_noun,
    _is_noise_dir_reference,
    _is_url_segment,
    _is_version_or_numeric_segment,
)


class TestUrlSegmentFilter:
    def test_actions_is_url_segment(self):
        assert _is_url_segment("actions") is True

    def test_badge_is_url_segment(self):
        assert _is_url_segment("badge") is True

    def test_blob_is_url_segment(self):
        assert _is_url_segment("blob") is True

    def test_src_is_not_url_segment(self):
        assert _is_url_segment("src") is False

    def test_backend_is_not_url_segment(self):
        assert _is_url_segment("backend") is False

    def test_case_insensitive(self):
        assert _is_url_segment("ACTIONS") is True
        assert _is_url_segment("Badge") is True


class TestNoiseFilters:
    def test_noise_dir_reference_filters_known_false_positives(self):
        for segment in ["TypeScript", "auth", "db", "8000", "Basic", "Key"]:
            assert _is_noise_dir_reference(segment) is True

    def test_noise_dir_reference_keeps_legitimate_repo_segments(self):
        for segment in [
            "MDS",
            "drift",
            "ingestion",
            "models",
            "myproject",
            "node_modules",
            "output",
            "path",
            "code",
            "home",
            "items",
            "user",
            "text",
            "IDE",
            "linters",
        ]:
            assert _is_noise_dir_reference(segment) is False

    def test_likely_proper_noun_true(self):
        assert _is_likely_proper_noun("TypeScript") is True
        assert _is_likely_proper_noun("Basic") is True

    def test_likely_proper_noun_false(self):
        assert _is_likely_proper_noun("src") is False
        assert _is_likely_proper_noun("utils") is False
        assert _is_likely_proper_noun("API") is False

    def test_version_or_numeric_segment_true(self):
        assert _is_version_or_numeric_segment("v1") is True
        assert _is_version_or_numeric_segment("v2_0") is True
        assert _is_version_or_numeric_segment("2024") is True
        assert _is_version_or_numeric_segment("20240315") is True

    def test_version_or_numeric_segment_false(self):
        assert _is_version_or_numeric_segment("src") is False
        assert _is_version_or_numeric_segment("api") is False
        # Short numeric fragments can be legitimate directory names
        assert _is_version_or_numeric_segment("42") is False


class TestMarkdownAstExtraction:
    def test_code_span_dir_ref(self):
        md = "Use the `src/` directory for source code."
        refs = _extract_dir_refs_from_ast(md)
        assert "src" in refs

    def test_fenced_code_block_skipped(self):
        """Fenced code blocks are skipped — they contain example code, not structure claims."""
        md = "# Project\n\n```bash\ncd internal/deploy/\n```\n"
        refs = _extract_dir_refs_from_ast(md)
        assert "internal" not in refs
        assert "deploy" not in refs

    def test_plain_text_dir_ref(self):
        md = "The backend/ folder contains the API."
        refs = _extract_dir_refs_from_ast(md)
        assert "backend" in refs

    def test_link_url_not_extracted(self):
        """Directory-like segments in link URLs should NOT be extracted."""
        md = "[![CI](https://github.com/user/repo/actions/badge/status.svg)](https://github.com/user/repo/actions/)"
        refs = _extract_dir_refs_from_ast(md)
        # 'actions' and 'badge' should NOT appear as refs
        assert "actions" not in refs
        assert "badge" not in refs

    def test_link_text_is_extracted(self):
        """Directory refs in link display text should be extracted."""
        md = "[see the src/ folder](https://example.com/docs)"
        refs = _extract_dir_refs_from_ast(md)
        assert "src" in refs

    def test_mixed_content(self):
        md = """\
# My Project

The `backend/` directory has the API code.

![Badge](https://img.shields.io/badge/status-ok-green.svg)

See [actions/deploy](https://github.com/user/repo/actions/) for CI.

The `frontend/` directory has the UI.
"""
        refs = _extract_dir_refs_from_ast(md)
        assert "backend" in refs
        assert "frontend" in refs
        # 'actions' from the link URL should not be extracted
        # but 'actions' from the link TEXT could be — that's acceptable
        # since the URL-segment filter will catch it downstream

    def test_empty_markdown(self):
        refs = _extract_dir_refs_from_ast("")
        assert refs == set()

    def test_no_dirs(self):
        md = "This is a simple readme with no directory references."
        refs = _extract_dir_refs_from_ast(md)
        assert refs == set()

    def test_proper_nouns_filtered(self):
        md = "We also support TypeScript/ and Basic/ examples."
        refs = _extract_dir_refs_from_ast(md)
        assert "TypeScript" not in refs
        assert "Basic" not in refs

    def test_version_segments_filtered(self):
        md = "See migration notes in v2/ and reports in 2024/."
        refs = _extract_dir_refs_from_ast(md)
        assert "v2" not in refs
        assert "2024" not in refs

    def test_single_char_segments_filtered(self):
        md = "Avoid e/ and i/ as accidental path fragments."
        refs = _extract_dir_refs_from_ast(md)
        assert "e" not in refs
        assert "i" not in refs

    def test_generic_slash_tokens_without_context_are_ignored(self):
        md = "CLI supports async/ scan/ connectors/ modes for examples."
        refs = _extract_dir_refs_from_ast(md)
        assert "async" not in refs
        assert "scan" not in refs
        assert "connectors" not in refs

    def test_plain_text_dir_with_structure_context_is_kept(self):
        md = "The connectors/ directory contains provider adapters."
        refs = _extract_dir_refs_from_ast(md)
        assert "connectors" in refs

    def test_backticked_path_without_context_is_kept(self):
        md = "Run checks in `scripts/` before packaging."
        refs = _extract_dir_refs_from_ast(md)
        assert "scripts" in refs


class TestAdrScanning:
    """Test ADR file scanning for phantom directory references."""

    def test_adr_phantom_dir_detected(self, tmp_path):
        """ADR referencing non-existent dir should produce a finding."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n- `src/` — code\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")
        (repo / "src" / "main.py").write_text("def main(): pass\n")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "# ADR 001\n\n- `controllers/` — HTTP layer\n"
            "- `repositories/` — data access\n"
        )

        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
        )
        files = discover_files(repo, config.include, config.exclude)
        parse_results = []
        for finfo in files:
            pr = parse_file(finfo.path, repo, finfo.language)
            parse_results.append(pr)

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, config)

        adr_findings = [
            f for f in findings if "ADR" in f.title
        ]
        referenced_dirs = {
            f.metadata.get("referenced_dir") for f in adr_findings
        }
        assert "controllers" in referenced_dirs
        assert "repositories" in referenced_dirs

    def test_adr_existing_dirs_no_finding(self, tmp_path):
        """ADR referencing existing dirs should NOT produce findings."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n- `src/` — code\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "# ADR 001\n\n- `src/` — main source code\n"
        )

        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
        )
        files = discover_files(repo, config.include, config.exclude)
        parse_results = []
        for finfo in files:
            pr = parse_file(finfo.path, repo, finfo.language)
            parse_results.append(pr)

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, config)

        adr_findings = [
            f for f in findings if "ADR" in f.title
        ]
        assert len(adr_findings) == 0

    def test_discovers_doc_decisions_directory(self, tmp_path):
        """Non-default ADR folder names should still be discovered."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n- `src/` — code\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        decisions = repo / "doc" / "decisions"
        decisions.mkdir(parents=True)
        (decisions / "0001.md").write_text(
            "# Decision\n\n- `controllers/` handles routing\n"
        )

        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
        )
        files = discover_files(repo, config.include, config.exclude)
        parse_results = []
        for finfo in files:
            pr = parse_file(finfo.path, repo, finfo.language)
            parse_results.append(pr)

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, config)

        assert any(
            f.title == "ADR references missing directory: controllers/"
            for f in findings
        )


class TestDiaLibraryContext:
    def test_library_layout_marks_context_candidate(self, tmp_path):
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Library\n\nUsage examples only.\n")
        (repo / "src").mkdir()
        (repo / "src" / "mylib.py").write_text("def public_api() -> None:\n    pass\n")

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        src_findings = [f for f in findings if f.metadata.get("undocumented_dir") == "src"]
        assert src_findings
        assert src_findings[0].metadata.get("library_context_candidate") is True
