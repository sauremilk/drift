import type { Scenario } from './index';

/**
 * Dead Code scenario — unused imports, unreachable functions, orphaned classes.
 *
 * Expected signals: PFS (pattern fragmentation from dead definitions)
 */
export const deadCodeScenario: Scenario = {
  id: 'dead-code',
  label: 'Dead Code',
  description:
    'Unused imports, unreachable functions, and abandoned classes accumulated over time — entropy made visible.',
  files: {
    'main.py': `"""Main application entry point — contains several dead-code patterns."""
import os
import json
import hashlib    # imported but never used in this module
import datetime   # imported but never used
import re         # imported but never used
from typing import List, Optional, Dict, Any  # most type aliases unused


# ── Dead constants ────────────────────────────────────────────────────────────
LEGACY_VERSION = "1.0.0"          # defined but never referenced
OLD_API_URL = "http://old.example.com/v1"  # dead constant
_INTERNAL_TIMEOUT = 30            # dead constant


# ── Dead function — defined but never called ─────────────────────────────────
def _legacy_process_data(data: List[Any]) -> Dict[str, Any]:
    """Old processing logic replaced by process() — still here."""
    result: Dict[str, Any] = {}
    for item in data:
        key = str(item.get("id", "unknown"))
        value = item.get("value", 0)
        result[key] = value * 2   # magic number 2 — should be a named constant
    return result


# ── Dead class — instantiated nowhere ────────────────────────────────────────
class DataValidator:
    """Validator class — only validate() is used externally; others are dead."""

    def __init__(self) -> None:
        self.rules: list = []
        self.errors: list = []

    def add_rule(self, rule: Any) -> None:   # never called
        self.rules.append(rule)

    def clear_errors(self) -> None:          # never called
        self.errors.clear()

    def run_all_rules(self, data: Any) -> bool:  # never called
        return all(rule(data) for rule in self.rules)

    def validate(self, data: Any) -> bool:   # only this method is actually used
        return data is not None


# ── Active code ───────────────────────────────────────────────────────────────
_validator = DataValidator()


def process(items: list) -> list:
    """Process a list of items — the only function called from outside."""
    return [{"processed": True, "value": item} for item in items if _validator.validate(item)]


def format_output(data: Any) -> str:
    """Serialize data to JSON."""
    return json.dumps(data, indent=2)


def save_to_file(data: Any, path: str) -> None:
    """Write JSON data to a file."""
    with open(path, "w") as fh:
        fh.write(format_output(data))


def main() -> None:
    items = [1, 2, 3, None, 5]
    processed = process(items)
    print(format_output(processed))


if __name__ == "__main__":
    main()
`,
    'utils.py': `"""Utility module — several functions are never imported or called."""
import os
from typing import Optional


# ── Dead utility functions ────────────────────────────────────────────────────

def never_called_utility(x: int, y: int) -> int:
    """Defined here but never imported or called anywhere."""
    return x + y


def also_unused(msg: str) -> Optional[str]:
    """Another unused function — should have been deleted."""
    if not msg:
        return None
    return msg.upper()


class UnusedMixin:
    """Mixin defined but never applied to any class."""

    def helper_method(self) -> str:
        return "unused"

    def another_helper(self, data: Any) -> Any:  # type: ignore[name-defined]
        return data


def _dead_internal_helper(path: str) -> bool:
    """Private helper — was used by a deleted function."""
    return os.path.exists(path)


# ── Active utilities ──────────────────────────────────────────────────────────

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


def chunk(lst: list, size: int) -> list[list]:
    """Split a list into fixed-size chunks."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]
`,
    'config.py': `"""Configuration loader — dead fallback functions accumulated here."""
import json
import os
from typing import Any


# Active config loading
def load_config(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


# Dead legacy functions — no longer called
def load_config_v1(path: str) -> dict:          # superseded by load_config
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def load_config_from_env() -> dict[str, Any]:   # replaced by environment-variable approach
    prefix = "APP_"
    return {
        k[len(prefix):].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


def merge_configs(*configs: dict) -> dict:      # dead — callers removed
    result: dict = {}
    for cfg in configs:
        result.update(cfg)
    return result


DEFAULT_CONFIG = {          # dead constant — nothing reads this anymore
    "debug": False,
    "port": 8080,
    "timeout": 30,
}
`,
  },
};
