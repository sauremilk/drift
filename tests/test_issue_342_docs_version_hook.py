from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_docs_version_module() -> object:
    module_path = Path(__file__).resolve().parents[1] / "hooks" / "docs_version.py"
    spec = importlib.util.spec_from_file_location("docs_version_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_version_reads_version_from_pyproject(tmp_path: Path) -> None:
    module = _load_docs_version_module()
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "2.6.0"\n', encoding="utf-8")

    assert module._extract_version(pyproject) == "2.6.0"


def test_extract_version_returns_none_when_missing_or_unmatched(tmp_path: Path) -> None:
    module = _load_docs_version_module()
    missing = tmp_path / "missing.toml"
    unmatched = tmp_path / "pyproject.toml"
    unmatched.write_text("[project]\nname = \"drift\"\n", encoding="utf-8")

    assert module._extract_version(missing) is None
    assert module._extract_version(unmatched) is None


def test_extract_latest_release_prefers_short_version_line(tmp_path: Path) -> None:
    module = _load_docs_version_module()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "\n".join(
            [
                "# Changelog",
                "",
                "## [Unreleased]",
                "",
                "## [2.6.0] - 2026-04-07",
                "Short version: Better scan precision",
                "",
            ]
        ),
        encoding="utf-8",
    )

    headline, date = module._extract_latest_release(changelog)

    assert headline == "Better scan precision"
    assert date == "2026-04-07"


def test_extract_latest_release_falls_back_to_date_without_short_version(tmp_path: Path) -> None:
    module = _load_docs_version_module()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "\n".join(
            [
                "# Changelog",
                "",
                "## [2.6.0] - 2026-04-07",
                "- Internal changes only",
            ]
        ),
        encoding="utf-8",
    )

    headline, date = module._extract_latest_release(changelog)

    assert headline is None
    assert date == "2026-04-07"


def test_on_config_injects_extra_metadata_and_caches_version(tmp_path: Path) -> None:
    module = _load_docs_version_module()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.6.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "\n".join(
            [
                "# Changelog",
                "",
                "## [2.6.0] - 2026-04-07",
                "Short version: Better scan precision",
            ]
        ),
        encoding="utf-8",
    )
    config = {"docs_dir": str(docs_dir), "extra": {}}

    result = module.on_config(config)

    assert result["extra"]["version"] == "2.6.0"
    assert result["extra"]["release_headline"] == "Better scan precision"
    assert result["extra"]["release_date"] == "2026-04-07"
    assert module._cached_version == "2.6.0"


def test_on_page_markdown_replaces_all_latest_tag_placeholders_when_cached() -> None:
    module = _load_docs_version_module()
    module._cached_version = "2.6.0"

    rendered = module.on_page_markdown("A DRIFT_LATEST_TAG and DRIFT_LATEST_TAG")

    assert rendered == "A v2.6.0 and v2.6.0"


def test_on_page_markdown_keeps_placeholder_without_cached_version() -> None:
    module = _load_docs_version_module()
    module._cached_version = None

    rendered = module.on_page_markdown("Tag: DRIFT_LATEST_TAG")

    assert rendered == "Tag: DRIFT_LATEST_TAG"
