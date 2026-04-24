"""Runtime tests for top-level CLI error handling in ``safe_main``."""

from __future__ import annotations

import json
import logging
import sys

import click
import pytest
from click.testing import CliRunner

from drift import cli


def _raise(exc: BaseException):
    def _inner(*args, **kwargs):
        raise exc

    return _inner


@pytest.fixture(autouse=True)
def _clear_error_format_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests control DRIFT_ERROR_FORMAT explicitly."""
    monkeypatch.delenv("DRIFT_ERROR_FORMAT", raising=False)


def test_safe_main_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "main", _raise(KeyboardInterrupt()))

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 130
    captured = capsys.readouterr()
    assert "Interrupted." in captured.err


def test_safe_main_file_not_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "main", _raise(FileNotFoundError("missing file")))

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 4
    captured = capsys.readouterr()
    assert "missing file" in captured.err
    assert "DRIFT-2001" in captured.err


def test_safe_main_generic_exception_shows_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "main", _raise(RuntimeError("boom")))
    logging.getLogger().setLevel(logging.WARNING)

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 3
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "DRIFT-3002" in captured.err
    assert "Hint: run with -v for the full traceback" in captured.err


def test_safe_main_generic_exception_prints_traceback_in_debug(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "main", _raise(RuntimeError("boom")))
    logging.getLogger().setLevel(logging.DEBUG)

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 3
    captured = capsys.readouterr()
    assert "DRIFT-3002" in captured.err
    assert "Traceback (most recent call last):" in captured.err
    assert "Hint: run with -v for the full traceback." not in captured.err


def test_safe_main_click_exception_is_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", _raise(click.ClickException("invalid")))

    with pytest.raises(click.ClickException):
        cli.safe_main()


def test_safe_main_exit_is_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", _raise(click.exceptions.Exit(2)))

    with pytest.raises(click.exceptions.Exit):
        cli.safe_main()


def test_handle_click_error_adds_did_you_mean_hint() -> None:
    command = click.Command("scan", params=[click.Option(["--max-findings"])])
    ctx = click.Context(command)
    exc = click.UsageError("No such option: --max-fndings", ctx=ctx)

    cli._handle_click_error(exc)

    assert "did you mean '--max-findings'" in exc.message


def test_handle_click_error_adds_subcommand_did_you_mean_hint() -> None:
    command = click.Group(
        "drift",
        commands={
            "analyze": click.Command("analyze"),
            "check": click.Command("check"),
        },
    )
    ctx = click.Context(command)
    exc = click.UsageError("No such command 'analze'.", ctx=ctx)

    cli._handle_click_error(exc)

    assert "did you mean 'analyze'" in exc.message


def test_runtime_unknown_subcommand_adds_did_you_mean_hint() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["analze"])

    assert result.exit_code != 0
    assert "No such command 'analze'" in result.output
    assert "did you mean 'analyze'" in result.output


def test_root_help_shows_curated_sections_and_core_path() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])

    assert result.exit_code == 0
    output = result.output
    assert "Start Here (80% Path):" in output
    assert "Investigation:" in output
    assert "Agent & MCP:" in output
    assert "CI & Automation:" in output
    assert "analyze" in output
    assert "fix-plan" in output
    assert "check" in output
    assert output.index("Start Here (80% Path):") < output.index("Investigation:")


def test_safe_main_drift_error_emits_json_payload_when_enabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from drift.errors import DriftConfigError

    def _raise_drift_error(*args, **kwargs):
        raise DriftConfigError(
            "DRIFT-1001",
            "bad config",
            config_path="drift.yaml",
            field="weights.pfs",
            reason="must be float",
            line=4,
        )

    monkeypatch.setenv("DRIFT_ERROR_FORMAT", "json")
    monkeypatch.setattr(cli, "main", _raise_drift_error)

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.err.strip())
    assert payload["schema_version"] == "2.2"
    assert payload["type"] == "error"
    assert payload["error_code"] == "DRIFT-1001"
    assert payload["category"] == "user"
    assert payload["exit_code"] == 2
    assert payload["recoverable"] is True
    assert payload["suggested_action"] is not None


def test_safe_main_generic_exception_emits_json_payload_when_enabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DRIFT_ERROR_FORMAT", "json")
    monkeypatch.setattr(cli, "main", _raise(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 3
    captured = capsys.readouterr()
    payload = json.loads(captured.err.strip())
    assert payload["schema_version"] == "2.2"
    assert payload["type"] == "error"
    assert payload["error_code"] == "DRIFT-3002"
    assert payload["category"] == "analysis"
    assert payload["exit_code"] == 3
    assert payload["message"] == "boom"
    assert payload["detail"].startswith("[DRIFT-3002]")
    assert payload["recoverable"] is False


def test_safe_main_enables_json_errors_for_format_json_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from drift.errors import DriftConfigError

    def _raise_drift_error(*args, **kwargs):
        raise DriftConfigError("DRIFT-1003", signal="INVALID")

    monkeypatch.delenv("DRIFT_ERROR_FORMAT", raising=False)
    monkeypatch.setattr(sys, "argv", ["drift", "self", "--format", "json"])
    monkeypatch.setattr(cli, "main", _raise_drift_error)

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] is True
    assert payload["error_code"] == "DRIFT-1003"


def test_safe_main_enables_json_errors_for_json_shortcut_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DRIFT_ERROR_FORMAT", raising=False)
    monkeypatch.setattr(sys, "argv", ["drift", "check", "--json"])
    monkeypatch.setattr(cli, "main", _raise(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 3
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] is True
    assert payload["error_code"] == "DRIFT-3002"


def test_safe_main_machine_mode_unknown_subcommand_emits_json_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DRIFT_ERROR_FORMAT", "json")
    monkeypatch.setattr(sys, "argv", ["drift", "anlyze"])

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err.strip()
    payload = json.loads(stderr)
    assert payload["error"] is True
    assert payload["error_code"] == "DRIFT-1010"
    assert payload["exit_code"] == 2
    assert "No such command" in payload["message"]
    assert "Usage:" not in stderr


def test_workers_zero_is_rejected_by_cli() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["analyze", "--workers", "0", "-q"])

    assert result.exit_code != 0
    assert "0" in result.output


def test_safe_main_scan_output_path_error_is_config_error_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    import drift.commands.scan as scan_command

    monkeypatch.setenv("DRIFT_ERROR_FORMAT", "json")
    monkeypatch.setattr(
        scan_command,
        "api_scan",
        lambda *args, **kwargs: {
            "schema_version": "2.2",
            "accept_change": True,
            "blocking_reasons": [],
        },
    )
    bad_output = tmp_path / "missing" / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drift",
            "scan",
            "--repo",
            str(tmp_path),
            "--output",
            str(bad_output),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["error"] is True
    assert payload["error_code"] == "DRIFT-2003"
    assert payload["exit_code"] == 2


def test_safe_main_fix_plan_invalid_signal_emits_single_json_and_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    import drift.commands.fix_plan as fix_plan_command

    monkeypatch.setenv("DRIFT_ERROR_FORMAT", "json")
    monkeypatch.setattr(
        fix_plan_command,
        "api_fix_plan",
        lambda *args, **kwargs: {
            "error": True,
            "schema_version": "2.2",
            "error_code": "DRIFT-1003",
            "message": "Unknown signal: 'INVALID_SIGNAL'",
            "invalid_fields": [
                {
                    "field": "signal",
                    "value": "INVALID_SIGNAL",
                    "reason": "Not a valid signal ID",
                }
            ],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drift",
            "fix-plan",
            "--repo",
            str(tmp_path),
            "--signal",
            "INVALID_SIGNAL",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.safe_main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    stderr = captured.err.strip()
    payload = json.loads(stderr)
    assert payload["error"] is True
    assert payload["error_code"] == "DRIFT-1012"
    assert payload["exit_code"] == 2
    assert payload["message"] == "Unknown signal: 'INVALID_SIGNAL'"
    assert "Usage:" not in stderr
