"""Persistence helpers for temporary fix-plan task dismissals."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_TTL_DAYS = 7
_DISMISSALS_FILE = "fix-plan-dismissed.json"


def _cache_file(repo_path: Path, cache_dir: str = ".drift-cache") -> Path:
    return repo_path / cache_dir / _DISMISSALS_FILE


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_iso8601_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_entries(repo_path: Path, cache_dir: str = ".drift-cache") -> list[dict[str, str]]:
    path = _cache_file(repo_path, cache_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_entries = payload.get("dismissed", [])
    elif isinstance(payload, list):
        raw_entries = payload
    else:
        raw_entries = []

    entries: list[dict[str, str]] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("task_id", "")).strip()
        expires_at = str(item.get("expires_at", "")).strip()
        dismissed_at = str(item.get("dismissed_at", "")).strip()
        if not task_id or not expires_at:
            continue
        entries.append(
            {
                "task_id": task_id,
                "expires_at": expires_at,
                "dismissed_at": dismissed_at,
            }
        )
    return entries


def _write_entries(
    repo_path: Path,
    entries: list[dict[str, str]],
    cache_dir: str = ".drift-cache",
) -> None:
    path = _cache_file(repo_path, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "dismissed": entries,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_active_dismissals(
    repo_path: Path,
    cache_dir: str = ".drift-cache",
    *,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    now_utc = now.astimezone(UTC) if now else _utcnow()
    active: list[dict[str, str]] = []

    for entry in _read_entries(repo_path, cache_dir):
        expires = _parse_iso8601(entry.get("expires_at"))
        if expires is None:
            continue
        if expires <= now_utc:
            continue
        active.append(entry)

    # Keep storage self-cleaning by dropping expired/invalid entries.
    _write_entries(repo_path, active, cache_dir)
    return active


def get_active_dismissal_ids(
    repo_path: Path,
    cache_dir: str = ".drift-cache",
    *,
    now: datetime | None = None,
) -> set[str]:
    return {entry["task_id"] for entry in get_active_dismissals(repo_path, cache_dir, now=now)}


def dismiss_task(
    repo_path: Path,
    task_id: str,
    cache_dir: str = ".drift-cache",
    *,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: datetime | None = None,
) -> dict[str, str]:
    now_utc = now.astimezone(UTC) if now else _utcnow()
    expiry = now_utc + timedelta(days=max(ttl_days, 1))

    active = [
        entry
        for entry in get_active_dismissals(repo_path, cache_dir, now=now_utc)
        if entry.get("task_id") != task_id
    ]
    record = {
        "task_id": task_id,
        "dismissed_at": _to_iso8601_utc(now_utc),
        "expires_at": _to_iso8601_utc(expiry),
    }
    active.append(record)
    _write_entries(repo_path, active, cache_dir)
    return record


def reset_dismissals(repo_path: Path, cache_dir: str = ".drift-cache") -> int:
    active = get_active_dismissals(repo_path, cache_dir)
    _write_entries(repo_path, [], cache_dir)
    return len(active)