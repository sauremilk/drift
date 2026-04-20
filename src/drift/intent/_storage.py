"""Persistent storage for CapturedIntent objects under .drift/intents/."""
from __future__ import annotations

from pathlib import Path

from ._models import CapturedIntent


def intent_store_path(intent_id: str, repo_root: Path = Path(".")) -> Path:
    """Return the JSON file path for a given intent_id under repo_root."""
    return repo_root / ".drift" / "intents" / f"{intent_id}.json"


def save_intent(intent: CapturedIntent, *, repo_root: Path = Path(".")) -> None:
    """Persist an intent to disk."""
    path = intent_store_path(intent.intent_id, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(intent.model_dump_json(indent=2), encoding="utf-8")


def load_intent(
    intent_id: str, *, repo_root: Path = Path(".")
) -> CapturedIntent | None:
    """Load a previously saved intent, or None if not found."""
    path = intent_store_path(intent_id, repo_root)
    if not path.exists():
        return None
    return CapturedIntent.model_validate_json(
        path.read_text(encoding="utf-8")
    )
