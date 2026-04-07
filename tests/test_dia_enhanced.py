"""Tests for the enhanced DIA (Markdown-AST + URL-filter)."""

from __future__ import annotations

from drift.signals.doc_impl_drift import (
    _extract_adr_status,
    _extract_dir_refs_from_ast,
    _is_likely_proper_noun,
    _is_noise_dir_reference,
    _is_url_segment,
    _is_version_or_numeric_segment,
    _ref_exists_in_repo,
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

    def test_backticked_path_with_context_is_kept(self):
        md = "The `scripts/` directory contains CI helpers."
        refs = _extract_dir_refs_from_ast(md)
        assert "scripts" in refs

    def test_backticked_path_without_context_is_filtered(self):
        """Inline code without structure keywords should NOT be extracted (CS-1 fix)."""
        md = "Run checks in `scripts/` before packaging."
        refs = _extract_dir_refs_from_ast(md)
        assert "scripts" not in refs


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


# ---------------------------------------------------------------------------
# CS-1 regression: codespan sibling-context gating
# ---------------------------------------------------------------------------


class TestCodespanSiblingContext:
    """Phase A: codespans should only be extracted when sibling text has keywords."""

    def test_codespan_with_directory_keyword(self):
        md = "The `services/` directory contains business logic."
        refs = _extract_dir_refs_from_ast(md)
        assert "services" in refs

    def test_codespan_with_folder_keyword(self):
        md = "Place modules in the `core/` folder."
        refs = _extract_dir_refs_from_ast(md)
        assert "core" in refs

    def test_codespan_with_structure_keyword(self):
        md = "Project structure: `services/` and `models/` hold the code."
        refs = _extract_dir_refs_from_ast(md)
        assert "services" in refs
        assert "models" in refs

    def test_codespan_without_keyword_is_filtered(self):
        """Inline code in prose without structure keywords -> no extraction (CS-1)."""
        md = "Send a request to `auth/callback` for login."
        refs = _extract_dir_refs_from_ast(md)
        assert "auth" not in refs

    def test_codespan_rest_path_without_context(self):
        md = "The endpoint is `users/profile` in production."
        refs = _extract_dir_refs_from_ast(md)
        assert "users" not in refs

    def test_codespan_see_for_more_without_context(self):
        md = "See `src/` for more information."
        refs = _extract_dir_refs_from_ast(md)
        assert "src" not in refs

    def test_codespan_with_package_keyword(self):
        md = "The package `utils/` provides helpers."
        refs = _extract_dir_refs_from_ast(md)
        assert "utils" in refs

    def test_heading_with_codespan_and_keyword(self):
        md = "## The `lib/` module\n\nCode goes here."
        refs = _extract_dir_refs_from_ast(md)
        assert "lib" in refs


# ---------------------------------------------------------------------------
# CS-2 regression: container-prefix existence check
# ---------------------------------------------------------------------------


class TestContainerPrefixExistence:
    """Phase B: directories under known container prefixes should be found."""

    def test_direct_path_exists(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "services").mkdir(parents=True)
        assert _ref_exists_in_repo(repo, "services", set()) is True

    def test_under_src_prefix(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "src" / "services").mkdir(parents=True)
        assert _ref_exists_in_repo(repo, "services", set()) is True

    def test_under_app_prefix(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "app" / "controllers").mkdir(parents=True)
        assert _ref_exists_in_repo(repo, "controllers", set()) is True

    def test_under_lib_prefix(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "lib" / "utils").mkdir(parents=True)
        assert _ref_exists_in_repo(repo, "utils", set()) is True

    def test_under_tests_not_container(self, tmp_path):
        """tests/ is NOT a container prefix -- should still report missing."""
        repo = tmp_path / "repo"
        (repo / "tests" / "services").mkdir(parents=True)
        assert _ref_exists_in_repo(repo, "services", set()) is False

    def test_in_source_dirs_case_insensitive(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        assert _ref_exists_in_repo(repo, "Services", {"services"}) is True

    def test_nonexistent_anywhere(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        assert _ref_exists_in_repo(repo, "phantom", set()) is False

    def test_e2e_src_prefix_no_finding(self, tmp_path):
        """Full signal: README refs services/, src/services/ exists -> no finding."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text(
            "# Project\n\nThe `services/` directory handles API logic.\n"
        )
        (repo / "src" / "services").mkdir(parents=True)
        (repo / "src" / "services" / "__init__.py").write_text("")
        (repo / "src" / "services" / "api.py").write_text("def handler(): pass\n")

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        phantom_findings = [
            f for f in findings if f.metadata.get("referenced_dir") == "services"
        ]
        assert len(phantom_findings) == 0


# ---------------------------------------------------------------------------
# CS-3 regression: ADR status parsing
# ---------------------------------------------------------------------------


class TestAdrStatusParsing:
    """Phase C: ADR status extraction and skip logic."""

    def test_yaml_frontmatter_accepted(self):
        text = "---\nid: ADR-001\nstatus: accepted\ndate: 2025-01-01\n---\n# ADR\n"
        assert _extract_adr_status(text) == "accepted"

    def test_yaml_frontmatter_superseded(self):
        text = "---\nstatus: superseded\n---\n# Old ADR\n"
        assert _extract_adr_status(text) == "superseded"

    def test_yaml_frontmatter_proposed(self):
        text = "---\nstatus: proposed\n---\n# ADR\n"
        assert _extract_adr_status(text) == "proposed"

    def test_yaml_frontmatter_case_insensitive(self):
        text = "---\nstatus: Superseded\n---\n# ADR\n"
        assert _extract_adr_status(text) == "superseded"

    def test_madr_heading_format(self):
        text = "# ADR 001\n\n## Status\n\nAccepted\n\n## Context\n"
        assert _extract_adr_status(text) == "accepted"

    def test_madr_heading_superseded(self):
        text = "# ADR 005\n\n## Status\n\nSuperseded by ADR-010\n\n## Context\n"
        assert _extract_adr_status(text) == "superseded"

    def test_no_status_returns_none(self):
        text = "# ADR 001\n\nSome description without a status.\n"
        assert _extract_adr_status(text) is None

    def test_superseded_adr_skipped_in_scan(self, tmp_path):
        """ADR with status: superseded should NOT produce findings."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` directory has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "---\nstatus: superseded\n---\n"
            "# ADR 001\n\n- `controllers/` — old HTTP layer\n"
        )

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        adr_findings = [f for f in findings if "ADR" in f.title]
        assert len(adr_findings) == 0

    def test_accepted_adr_still_produces_findings(self, tmp_path):
        """ADR with status: accepted should still produce findings for phantom dirs."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` directory has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "---\nstatus: accepted\n---\n"
            "# ADR 001\n\n- `controllers/` — HTTP layer\n"
        )

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        adr_findings = [f for f in findings if "ADR" in f.title]
        assert any(f.metadata.get("referenced_dir") == "controllers" for f in adr_findings)

    def test_no_status_adr_still_produces_findings(self, tmp_path):
        """ADR without status field should still produce findings (conservative)."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` directory has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "# ADR 001\n\n- `controllers/` — HTTP layer\n"
        )

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        adr_findings = [f for f in findings if "ADR" in f.title]
        assert any(f.metadata.get("referenced_dir") == "controllers" for f in adr_findings)

    def test_madr_superseded_format_skipped(self, tmp_path):
        """ADR with MADR heading Status: Superseded should be skipped."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` directory has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "__init__.py").write_text("")

        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "001.md").write_text(
            "# ADR 001\n\n## Status\n\nSuperseded by ADR-005\n\n"
            "## Context\n\n- `controllers/` — old layer\n"
        )

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        adr_findings = [f for f in findings if "ADR" in f.title]
        assert len(adr_findings) == 0


# ---------------------------------------------------------------------------
# P5 regression: slash-continuation negative lookahead (?!\w)
# ---------------------------------------------------------------------------


class TestSlashContinuationGuard:
    """P5: word/ followed by another word char should NOT be extracted."""

    def test_try_except_not_extracted(self):
        md = "Use `try/except` for error handling."
        refs = _extract_dir_refs_from_ast(md, trust_codespans=True)
        assert "try" not in refs

    def test_match_case_not_extracted(self):
        md = "Python 3.10 introduces `match/case` syntax."
        refs = _extract_dir_refs_from_ast(md, trust_codespans=True)
        assert "match" not in refs

    def test_parent_tree_not_extracted(self):
        md = "Navigate the parent/tree references carefully."
        refs = _extract_dir_refs_from_ast(md)
        assert "parent" not in refs

    def test_multisegment_path_extracts_terminal_only(self):
        """src/drift/output/csv_output.py → nothing extracted (all segments have continuations)."""
        md = "See `src/drift/output/csv_output.py` for the module."
        refs = _extract_dir_refs_from_ast(md, trust_codespans=True)
        assert "src" not in refs
        assert "drift" not in refs
        assert "output" not in refs

    def test_trailing_slash_still_extracted(self):
        """A terminal segment like `output/` (with trailing slash) IS extracted."""
        md = "The `output/` directory has formatters."
        refs = _extract_dir_refs_from_ast(md)
        assert "output" in refs

    def test_standalone_dir_ref_still_works(self):
        md = "The `controllers/` directory handles HTTP."
        refs = _extract_dir_refs_from_ast(md)
        assert "controllers" in refs

    def test_multisegment_trailing_slash_extracts_last(self):
        """src/drift/output/ → only output is extracted (trailing slash)."""
        md = "The `src/drift/output/` directory has formatters."
        refs = _extract_dir_refs_from_ast(md)
        assert "output" in refs
        assert "src" not in refs
        assert "drift" not in refs


# ---------------------------------------------------------------------------
# P3 regression: URL stripping before regex
# ---------------------------------------------------------------------------


class TestUrlStripGuard:
    """P3: URLs in plain text should not produce dir-ref extractions."""

    def test_github_url_not_extracted(self):
        md = "Visit https://github.com/mick-gsk/drift for more info."
        refs = _extract_dir_refs_from_ast(md)
        assert "mick-gsk" not in refs
        assert "drift" not in refs

    def test_github_url_with_trailing_slash(self):
        md = "See https://github.com/some-org/ for the org page."
        refs = _extract_dir_refs_from_ast(md)
        assert "some-org" not in refs

    def test_non_url_text_still_extracted(self):
        md = "The `services/` directory handles business logic."
        refs = _extract_dir_refs_from_ast(md)
        assert "services" in refs


# ---------------------------------------------------------------------------
# P6 regression: dotfile prefix existence check
# ---------------------------------------------------------------------------


class TestDotfilePrefixExistence:
    """P6: .drift-cache/ should match ref 'drift-cache' via dotfile prefix."""

    def test_dotfile_prefix_found(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".drift-cache").mkdir()
        assert _ref_exists_in_repo(repo, "drift-cache", set()) is True

    def test_dotfile_prefix_not_found(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        assert _ref_exists_in_repo(repo, "drift-cache", set()) is False

    def test_dotfile_must_be_dir(self, tmp_path):
        """Only directories count — a file named .drift-cache should not match."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".drift-cache").write_text("not a dir")
        assert _ref_exists_in_repo(repo, "drift-cache", set()) is False


# ---------------------------------------------------------------------------
# P1 regression: auxiliary directory exclusion
# ---------------------------------------------------------------------------


class TestAuxiliaryDirExclusion:
    """P1: conventional project dirs should not produce undocumented-dir findings."""

    def test_tests_dir_not_flagged(self, tmp_path):
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` directory has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("x = 1\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_main.py").write_text("def test_x(): pass\n")
        (repo / "scripts").mkdir()
        (repo / "scripts" / "deploy.py").write_text("x = 1\n")
        (repo / "benchmarks").mkdir()
        (repo / "benchmarks" / "bench.py").write_text("x = 1\n")

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        undoc = {
            f.metadata.get("undocumented_dir") for f in findings
            if f.metadata.get("undocumented_dir")
        }
        assert "tests" not in undoc
        assert "scripts" not in undoc
        assert "benchmarks" not in undoc

    def test_nonaux_dir_still_flagged(self, tmp_path):
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\nJust a readme.\n")
        (repo / "services").mkdir()
        (repo / "services" / "api.py").write_text("x = 1\n")

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        undoc = {
            f.metadata.get("undocumented_dir") for f in findings
            if f.metadata.get("undocumented_dir")
        }
        assert "services" in undoc

    def test_artifacts_dir_not_flagged(self, tmp_path):
        """work_artifacts and artifacts dirs are conventional auxiliary dirs."""
        from drift.config import DriftConfig
        from drift.ingestion.ast_parser import parse_file
        from drift.ingestion.file_discovery import discover_files
        from drift.signals.doc_impl_drift import DocImplDriftSignal

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Project\n\n`src/` has code.\n")
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("x = 1\n")
        (repo / "work_artifacts").mkdir()
        (repo / "work_artifacts" / "probe.py").write_text("x = 1\n")
        (repo / "artifacts").mkdir()
        (repo / "artifacts" / "helper.py").write_text("x = 1\n")

        cfg = DriftConfig(include=["**/*.py"], exclude=["**/__pycache__/**"])
        files = discover_files(repo, cfg.include, cfg.exclude)
        parse_results = [parse_file(f.path, repo, f.language) for f in files]

        signal = DocImplDriftSignal(repo_path=repo)
        findings = signal.analyze(parse_results, {}, cfg)

        undoc = {
            f.metadata.get("undocumented_dir") for f in findings
            if f.metadata.get("undocumented_dir")
        }
        assert "work_artifacts" not in undoc
        assert "artifacts" not in undoc


class TestAdrFencedCodeBlockSkipped:
    """Illustrative dir refs inside fenced code blocks in ADRs must not be extracted."""

    def test_fenced_block_services_not_extracted(self):
        md = (
            "# ADR-017\n\n"
            "- **CS-2:** Pfad-Normalisierung erkennt Container-Prefixe nicht:\n"
            "  ```\n"
            "  src/services/\n"
            "  ```\n"
            "  weil nur parts[0] in source_dirs aufgenommen wird.\n"
        )
        refs = _extract_dir_refs_from_ast(md, trust_codespans=True)
        assert "services" not in refs

    def test_inline_codespan_still_extracted(self):
        md = "The `services/` directory has handlers.\n"
        refs = _extract_dir_refs_from_ast(md, trust_codespans=True)
        assert "services" in refs
