from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "fetch_pypistats.py"
    spec = importlib.util.spec_from_file_location("fetch_pypistats", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_aggregate_monthly_downloads_filters_and_sums() -> None:
    module = _load_module()
    rows = [
        {"date": "2026-01-01", "category": "without_mirrors", "downloads": 10},
        {"date": "2026-01-02", "category": "without_mirrors", "downloads": 5},
        {"date": "2026-01-03", "category": "with_mirrors", "downloads": 999},
        {"date": "2026-02-01", "category": "without_mirrors", "downloads": 7},
    ]

    monthly = module._aggregate_monthly_downloads(rows)

    assert monthly == {"2026-01": 15, "2026-02": 7}


def test_aggregate_monthly_downloads_ignores_bad_rows() -> None:
    module = _load_module()
    rows = [
        {"date": "bad-date", "category": "without_mirrors", "downloads": 10},
        {"date": "2026-01-01", "category": "without_mirrors", "downloads": "NaN"},
    ]

    monthly = module._aggregate_monthly_downloads(rows)

    assert monthly == {}
