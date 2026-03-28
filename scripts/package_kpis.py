"""Compute a practical monthly KPI set for a PyPI package.

KPIs:
- MAUP (Monthly Active Using Projects)
- 90-day retention (month-to-month+3 project overlap)
- Upgrade currency rate (share of active projects on allowed versions)
- Quality friction per 100 active projects (confirmed package-related defects)
- TTM (median days to mitigation) for critical defects

Input format
------------
Usage CSV (required):
  timestamp,project_id,version
  2026-01-10T12:00:00Z,acme.api,1.2.0

Defects CSV (optional):
  confirmed_at,fixed_at,severity,package_related
  2026-01-15T09:00:00Z,2026-01-20T18:00:00Z,critical,true

Usage:
  python scripts/package_kpis.py \
    --package drift-analyzer \
    --usage-csv data/usage.csv \
    --defects-csv data/defects.csv \
    --currency-versions 1.4.0,1.3.2 \
    --months 12 \
    --output benchmark_results/package_kpis.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MetricThresholds = dict[str, dict[str, object]]


@dataclass(frozen=True)
class UsageEvent:
    timestamp: datetime
    project_id: str
    version: str


@dataclass(frozen=True)
class DefectEvent:
    confirmed_at: datetime
    fixed_at: datetime | None
    severity: str
    package_related: bool


def _parse_iso8601(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _month_key(value: datetime) -> str:
    return value.strftime("%Y-%m")


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


def _read_usage_csv(path: Path) -> list[UsageEvent]:
    events: list[UsageEvent] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=2):
            try:
                timestamp_raw = row["timestamp"]
                project_id = row["project_id"].strip()
                version = row["version"].strip()
            except KeyError as exc:
                raise ValueError(
                    "Usage CSV must contain: timestamp, project_id, version"
                ) from exc
            if not project_id or not version:
                raise ValueError(f"Usage CSV row {idx} has empty project_id/version")
            events.append(
                UsageEvent(
                    timestamp=_parse_iso8601(timestamp_raw),
                    project_id=project_id,
                    version=version,
                )
            )
    return events


def _read_defects_csv(path: Path) -> list[DefectEvent]:
    events: list[DefectEvent] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                confirmed_raw = row["confirmed_at"]
                fixed_raw = row.get("fixed_at", "")
                severity = row.get("severity", "").strip().lower() or "unknown"
                related_raw = row.get("package_related", "true")
            except KeyError as exc:
                raise ValueError(
                    "Defects CSV must contain: confirmed_at, fixed_at, severity, package_related"
                ) from exc

            fixed_at = _parse_iso8601(fixed_raw) if fixed_raw and fixed_raw.strip() else None
            events.append(
                DefectEvent(
                    confirmed_at=_parse_iso8601(confirmed_raw),
                    fixed_at=fixed_at,
                    severity=severity,
                    package_related=_parse_bool(related_raw),
                )
            )
    return events


def _read_monthly_downloads_csv(path: Path) -> dict[str, int]:
    monthly: dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            month = str(row.get("month", "")).strip()
            if len(month) != 7 or month[4] != "-":
                continue
            try:
                downloads = int(str(row.get("downloads", "0")).strip())
            except ValueError:
                continue
            monthly[month] = downloads
    return monthly


def _read_thresholds_json(path: Path) -> MetricThresholds:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Thresholds JSON must be an object")
    return data


def _metric_status(value: object, rule: dict[str, object]) -> str:
    if value is None:
        return "no-data"

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "no-data"

    direction = str(rule.get("direction", "higher_is_better"))
    green = rule.get("green")
    yellow = rule.get("yellow")
    if green is None or yellow is None:
        return "no-data"

    green_val = float(green)
    yellow_val = float(yellow)

    if direction == "lower_is_better":
        if numeric <= green_val:
            return "green"
        if numeric <= yellow_val:
            return "yellow"
        return "red"

    if numeric >= green_val:
        return "green"
    if numeric >= yellow_val:
        return "yellow"
    return "red"


def _evaluate_statuses(row: dict[str, object], thresholds: MetricThresholds) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for metric, rule in thresholds.items():
        if not isinstance(rule, dict):
            statuses[metric] = "no-data"
            continue
        statuses[metric] = _metric_status(row.get(metric), rule)
    return statuses


def _add_months(month: str, delta: int) -> str:
    year_s, month_s = month.split("-")
    year = int(year_s)
    month_i = int(month_s)
    total = year * 12 + (month_i - 1) + delta
    new_year = total // 12
    new_month = (total % 12) + 1
    return f"{new_year:04d}-{new_month:02d}"


def compute_monthly_kpis(
    usage_events: list[UsageEvent],
    defect_events: list[DefectEvent] | None = None,
    currency_versions: set[str] | None = None,
    months: int | None = None,
    downloads_by_month: dict[str, int] | None = None,
    thresholds: MetricThresholds | None = None,
) -> list[dict[str, object]]:
    downloads_by_month = downloads_by_month or {}
    thresholds = thresholds or {}

    if not usage_events and not downloads_by_month:
        return []

    defect_events = defect_events or []
    currency_versions = currency_versions or set()

    projects_by_month: dict[str, set[str]] = {}
    currency_projects_by_month: dict[str, set[str]] = {}

    for event in usage_events:
        month = _month_key(event.timestamp)
        projects_by_month.setdefault(month, set()).add(event.project_id)
        if event.version in currency_versions:
            currency_projects_by_month.setdefault(month, set()).add(event.project_id)

    defects_by_month: dict[str, list[DefectEvent]] = {}
    for event in defect_events:
        month = _month_key(event.confirmed_at)
        defects_by_month.setdefault(month, []).append(event)

    month_keys = sorted(set(projects_by_month) | set(downloads_by_month))
    if months is not None and months > 0:
        month_keys = month_keys[-months:]

    output: list[dict[str, object]] = []

    for month in month_keys:
        active_projects = projects_by_month.get(month, set())
        maup = len(active_projects)

        future_month = _add_months(month, 3)
        if future_month in projects_by_month:
            retained = len(active_projects & projects_by_month[future_month])
            retention_90 = (retained / maup) if maup else None
        else:
            retention_90 = None

        currency_projects = currency_projects_by_month.get(month, set())
        currency_rate = (len(currency_projects) / maup) if (maup and currency_versions) else None

        month_defects = [d for d in defects_by_month.get(month, []) if d.package_related]
        friction = (len(month_defects) / maup * 100.0) if maup else None

        critical_ttm_days: list[float] = []
        for defect in month_defects:
            if defect.severity != "critical" or defect.fixed_at is None:
                continue
            delta = defect.fixed_at - defect.confirmed_at
            critical_ttm_days.append(delta.total_seconds() / 86400.0)

        ttm_critical_median_days = (
            statistics.median(critical_ttm_days) if critical_ttm_days else None
        )

        row = {
            "month": month,
            "maup": maup,
            "retention_90d": retention_90,
            "currency_rate": currency_rate,
            "friction_per_100_projects": friction,
            "ttm_critical_median_days": ttm_critical_median_days,
            "defect_count": len(month_defects),
            "pypi_downloads": downloads_by_month.get(month),
        }
        if thresholds:
            row["status"] = _evaluate_statuses(row, thresholds)
        output.append(row)

    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute monthly package KPIs from CSV inputs")
    parser.add_argument("--package", required=True, help="Package name for metadata")
    parser.add_argument("--usage-csv", type=Path, required=True, help="CSV with usage events")
    parser.add_argument("--defects-csv", type=Path, default=None, help="Optional CSV with defects")
    parser.add_argument(
        "--currency-versions",
        default="",
        help="Comma-separated versions considered current (e.g. latest and N-1)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=12,
        help="Trailing number of months to export (default: 12)",
    )
    parser.add_argument(
        "--downloads-csv",
        type=Path,
        default=None,
        help="Optional CSV with monthly downloads (columns: month,downloads)",
    )
    parser.add_argument(
        "--thresholds-json",
        type=Path,
        default=None,
        help="Optional KPI threshold policy JSON for status evaluation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark_results/package_kpis.json"),
        help="Output JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    usage_events = _read_usage_csv(args.usage_csv)
    defects = _read_defects_csv(args.defects_csv) if args.defects_csv else []
    downloads_by_month = (
        _read_monthly_downloads_csv(args.downloads_csv) if args.downloads_csv else {}
    )
    thresholds = _read_thresholds_json(args.thresholds_json) if args.thresholds_json else {}
    currency_versions = {
        value.strip() for value in args.currency_versions.split(",") if value.strip()
    }

    monthly = compute_monthly_kpis(
        usage_events=usage_events,
        defect_events=defects,
        currency_versions=currency_versions,
        months=args.months,
        downloads_by_month=downloads_by_month,
        thresholds=thresholds,
    )

    payload = {
        "package": args.package,
        "generated_at": datetime.now(UTC).isoformat(),
        "currency_versions": sorted(currency_versions),
        "thresholds_enabled": bool(thresholds),
        "kpis": monthly,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote KPI report to {args.output}")


if __name__ == "__main__":
    main()
