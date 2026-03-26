from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "check_release_discipline.py"
    spec = importlib.util.spec_from_file_location("check_release_discipline", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_release_bullets_only_from_curated_sections():
    module = _load_module()
    body = """
Short version: short summary.

### Added
- First bullet

### Notes
- Ignore this note

### Fixed
- Second bullet
""".strip()

    bullets = module._collect_release_bullets(body)
    assert bullets == ["- First bullet", "- Second bullet"]


def test_validate_summary_requires_short_version_line():
    module = _load_module()

    try:
        module._validate_summary("### Added\n- Something")
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("Expected SystemExit for missing short version line")


def test_validate_curated_bullets_rejects_commit_dump_style():
    module = _load_module()
    body = """
Short version: summary.

### Added
- feat: raw commit replay
""".strip()

    try:
        module._validate_curated_bullets(body)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("Expected SystemExit for raw commit style bullet")


def test_validate_curated_bullets_rejects_more_than_five_bullets():
    module = _load_module()
    body = """
Short version: summary.

### Added
- One
- Two
- Three
### Changed
- Four
- Five
### Fixed
- Six
""".strip()

    try:
        module._validate_curated_bullets(body)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("Expected SystemExit for too many bullets")
