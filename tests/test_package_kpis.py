from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "package_kpis.py"
    spec = importlib.util.spec_from_file_location("package_kpis", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_compute_monthly_kpis_core_metrics() -> None:
    module = _load_module()

    usage = [
        module.UsageEvent(timestamp=_ts("2026-01-05T00:00:00"), project_id="a", version="1.4.0"),
        module.UsageEvent(timestamp=_ts("2026-01-11T00:00:00"), project_id="b", version="1.3.2"),
        module.UsageEvent(timestamp=_ts("2026-01-20T00:00:00"), project_id="c", version="1.2.0"),
        module.UsageEvent(timestamp=_ts("2026-04-01T00:00:00"), project_id="a", version="1.4.0"),
        module.UsageEvent(timestamp=_ts("2026-04-03T00:00:00"), project_id="x", version="1.4.0"),
    ]
    defects = [
        module.DefectEvent(
            confirmed_at=_ts("2026-01-10T00:00:00"),
            fixed_at=_ts("2026-01-13T00:00:00"),
            severity="critical",
            package_related=True,
        ),
        module.DefectEvent(
            confirmed_at=_ts("2026-01-20T00:00:00"),
            fixed_at=None,
            severity="medium",
            package_related=True,
        ),
    ]

    rows = module.compute_monthly_kpis(
        usage_events=usage,
        defect_events=defects,
        currency_versions={"1.4.0", "1.3.2"},
        months=None,
    )

    january = rows[0]
    assert january["month"] == "2026-01"
    assert january["maup"] == 3
    assert january["retention_90d"] == 1 / 3
    assert january["currency_rate"] == 2 / 3
    assert january["defect_count"] == 2
    assert january["friction_per_100_projects"] == (2 / 3) * 100
    assert january["ttm_critical_median_days"] == 3.0
    assert january["pypi_downloads"] is None


def test_compute_monthly_kpis_retention_is_none_without_future_month() -> None:
    module = _load_module()
    usage = [
        module.UsageEvent(timestamp=_ts("2026-02-01T00:00:00"), project_id="a", version="1.0.0"),
    ]

    rows = module.compute_monthly_kpis(usage_events=usage, months=None)

    assert rows[0]["month"] == "2026-02"
    assert rows[0]["retention_90d"] is None
    assert rows[0]["currency_rate"] is None


def test_parse_bool_variants() -> None:
    module = _load_module()

    assert module._parse_bool("true") is True
    assert module._parse_bool("YES") is True
    assert module._parse_bool("1") is True
    assert module._parse_bool("false") is False
    assert module._parse_bool("0") is False


def test_compute_monthly_kpis_merges_downloads() -> None:
    module = _load_module()
    usage = [
        module.UsageEvent(timestamp=_ts("2026-01-01T00:00:00"), project_id="a", version="1.0.0"),
    ]

    rows = module.compute_monthly_kpis(
        usage_events=usage,
        downloads_by_month={"2026-01": 1234, "2026-02": 999},
        months=None,
    )

    assert rows[0]["month"] == "2026-01"
    assert rows[0]["pypi_downloads"] == 1234
    assert rows[1]["month"] == "2026-02"
    assert rows[1]["maup"] == 0
    assert rows[1]["pypi_downloads"] == 999


def test_compute_monthly_kpis_downloads_only() -> None:
    module = _load_module()

    rows = module.compute_monthly_kpis(
        usage_events=[],
        downloads_by_month={"2026-03": 42},
        months=None,
    )

    assert rows == [
        {
            "month": "2026-03",
            "maup": 0,
            "retention_90d": None,
            "currency_rate": None,
            "friction_per_100_projects": None,
            "ttm_critical_median_days": None,
            "defect_count": 0,
            "pypi_downloads": 42,
        }
    ]


def test_metric_status_higher_and_lower() -> None:
    module = _load_module()

    assert (
        module._metric_status(0.82, {"direction": "higher_is_better", "green": 0.8, "yellow": 0.6})
        == "green"
    )
    assert (
        module._metric_status(0.65, {"direction": "higher_is_better", "green": 0.8, "yellow": 0.6})
        == "yellow"
    )
    assert (
        module._metric_status(0.4, {"direction": "higher_is_better", "green": 0.8, "yellow": 0.6})
        == "red"
    )

    assert (
        module._metric_status(1.8, {"direction": "lower_is_better", "green": 2.0, "yellow": 4.0})
        == "green"
    )
    assert (
        module._metric_status(3.0, {"direction": "lower_is_better", "green": 2.0, "yellow": 4.0})
        == "yellow"
    )
    assert (
        module._metric_status(8.0, {"direction": "lower_is_better", "green": 2.0, "yellow": 4.0})
        == "red"
    )


def test_compute_monthly_kpis_adds_status_when_thresholds_enabled() -> None:
    module = _load_module()
    usage = [
        module.UsageEvent(timestamp=_ts("2026-01-01T00:00:00"), project_id="a", version="1.0.0"),
    ]

    thresholds = {
        "maup": {"direction": "higher_is_better", "green": 5, "yellow": 2},
        "friction_per_100_projects": {"direction": "lower_is_better", "green": 10, "yellow": 25},
    }
    rows = module.compute_monthly_kpis(
        usage_events=usage,
        thresholds=thresholds,
        months=None,
    )

    assert rows[0]["status"]["maup"] == "red"
    assert rows[0]["status"]["friction_per_100_projects"] == "green"
