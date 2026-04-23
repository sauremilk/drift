import type { Scenario } from './index';

/**
 * Circular Dependencies scenario — three modules that form a cycle:
 * processor → formatter → validator → processor
 *
 * Expected signals: MDS (module dependency score)
 */
export const circularDepsScenario: Scenario = {
  id: 'circular-deps',
  label: 'Circular Dependencies',
  description:
    'Three modules that import each other in a cycle, making the codebase brittle and hard to test in isolation.',
  files: {
    'processor.py': `"""Data processor — imports from formatter, creating a dependency cycle."""
from formatter import format_result  # formatter → validator → processor (cycle!)
from validator import validate_input


def process(data: dict) -> dict:
    """Process raw data through validation and formatting."""
    if not validate_input(data):
        return {"error": "invalid input", "data": None}

    result = {
        "processed": True,
        "value": data.get("value", 0) * 2,
        "source": "processor",
    }
    return format_result(result)


def process_batch(items: list[dict]) -> list[dict]:
    """Process a list of items."""
    return [process(item) for item in items]


def run_pipeline(raw: dict) -> dict:
    """Run the full processing pipeline."""
    validated = validate_input(raw)
    if not validated:
        return {"status": "rejected"}
    processed = process(raw)
    return format_result(processed)
`,
    'formatter.py': `"""Output formatter — imports from validator, part of the dependency cycle."""
from validator import validate_output  # validator → processor → formatter (cycle closure)


def format_result(data: dict) -> dict:
    """Format a result dict for output."""
    if not isinstance(data, dict):
        return {"formatted": False, "error": "expected dict"}

    formatted = {
        "formatted": True,
        "timestamp": "2026-04-23T00:00:00Z",
        "payload": {k: str(v) for k, v in data.items()},
    }

    if not validate_output(formatted):
        formatted["warning"] = "output validation failed"

    return formatted


def format_error(message: str) -> dict:
    """Wrap an error message in the standard format."""
    return {"formatted": True, "error": True, "message": message}


def format_batch(results: list[dict]) -> list[dict]:
    return [format_result(r) for r in results]
`,
    'validator.py': `"""Input/output validator — imports from processor, closing the cycle."""
from processor import process  # Creates the cycle: validator → processor → formatter → validator


def validate_input(data: dict) -> bool:
    """Check that input data meets requirements."""
    if not isinstance(data, dict):
        return False
    if "value" not in data:
        return False
    return isinstance(data["value"], (int, float))


def validate_output(data: dict) -> bool:
    """Check that formatted output is well-formed."""
    return isinstance(data, dict) and data.get("formatted") is True


def validate_and_process(data: dict) -> dict:
    """Validate then immediately process — tightens the coupling further."""
    if not validate_input(data):
        return {"valid": False}
    return process(data)


def check_batch(items: list[dict]) -> list[bool]:
    return [validate_input(item) for item in items]
`,
    'utils.py': `"""Utilities used across the circular-dependent modules."""
import json
from typing import Any


def to_json(obj: Any) -> str:
    return json.dumps(obj, default=str)


def from_json(s: str) -> Any:
    return json.loads(s)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
`,
  },
};
