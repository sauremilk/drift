from __future__ import annotations

import json

from scripts import evaluate_benchmark


def test_finding_keys_include_stable_and_legacy_formats() -> None:
    finding = {
        "signal": "architecture_violation",
        "title": "Upward import detected",
        "file_path": "db/models.py",
        "line": 42,
    }

    keys = evaluate_benchmark._finding_keys("sample_repo", finding)

    assert keys[0] == (
        "sample_repo::architecture_violation::db/models.py:42::Upward import detected"
    )
    assert keys[1] == "sample_repo::Upward import detected"


def test_load_labels_supports_legacy_alias(tmp_path) -> None:
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "key": "repo::signal::path.py:10::Title",
                    "legacy_key": "repo::Title",
                    "label": "TP",
                }
            ]
        ),
        encoding="utf-8",
    )

    original = evaluate_benchmark.LABELS_FILE
    evaluate_benchmark.LABELS_FILE = labels_path
    try:
        labels = evaluate_benchmark._load_labels()
    finally:
        evaluate_benchmark.LABELS_FILE = original

    assert labels["repo::signal::path.py:10::Title"] == "TP"
    assert labels["repo::Title"] == "TP"
