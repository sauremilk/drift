from pathlib import Path


def test_issue_353_action_uses_drift_ci_for_execution() -> None:
    action_path = Path(__file__).resolve().parents[1] / "action.yml"
    content = action_path.read_text(encoding="utf-8")

    assert "drift ci ${ARGS}" in content
    assert "drift check ${ARGS}" not in content
