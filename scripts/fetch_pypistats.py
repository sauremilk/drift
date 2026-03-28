"""Fetch real monthly download counts from PyPIStats API.

Usage:
  python scripts/fetch_pypistats.py \
    --package drift-analyzer \
    --months 12 \
    --output benchmark_results/package_kpis/pypi_downloads_monthly.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _month_key(date_str: str) -> str:
    # Expected input from API: YYYY-MM-DD
    return date_str[:7]


def _aggregate_monthly_downloads(rows: list[dict[str, object]]) -> dict[str, int]:
    monthly: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("category") not in {"without_mirrors", "overall"}:
            continue
        date_value = str(row.get("date", ""))
        month = _month_key(date_value)
        if len(month) != 7 or month[4] != "-":
            continue
        try:
            downloads = int(str(row.get("downloads", 0)))
        except (TypeError, ValueError):
            continue
        monthly[month] += downloads
    return dict(sorted(monthly.items()))


def _fetch_overall(package: str, timeout: int) -> list[dict[str, object]]:
    url = f"https://pypistats.org/api/packages/{package}/overall?mirrors=false"
    request = Request(url, headers={"User-Agent": "drift-package-kpis/1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    return list(payload.get("data", []))


def _write_monthly_csv(path: Path, monthly: dict[str, int], months: int) -> None:
    items = sorted(monthly.items())
    if months > 0:
        items = items[-months:]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["month", "downloads"])
        for month, downloads in items:
            writer.writerow([month, downloads])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch monthly PyPI download counts")
    parser.add_argument("--package", required=True, help="PyPI package name")
    parser.add_argument("--months", type=int, default=12, help="Trailing months to export")
    parser.add_argument(
        "--timeout", type=int, default=30, help="HTTP timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark_results/package_kpis/pypi_downloads_monthly.csv"),
        help="Target CSV path",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        rows = _fetch_overall(args.package, args.timeout)
    except HTTPError as exc:
        raise SystemExit(f"PyPIStats HTTP error: {exc.code}") from exc
    except URLError as exc:
        raise SystemExit(f"PyPIStats network error: {exc.reason}") from exc

    monthly = _aggregate_monthly_downloads(rows)
    _write_monthly_csv(args.output, monthly, args.months)

    print(
        f"Fetched {len(rows)} rows, wrote {min(len(monthly), args.months)} months to {args.output}"
    )
    print(f"Generated at {datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    main()
