"""Runtime tests for top-level CLI error handling in ``safe_main``."""

from __future__ import annotations

import json
import logging

import click
import pytest

from drift import cli


def _raise(exc: BaseException):
    def _inner(*args, **kwargs):
        raise exc

    return _inner


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
    assert "Hint: run with -v for the full traceback." in captured.err


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
    assert payload["schema_version"] == "2.0"
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
    assert payload["schema_version"] == "2.0"
    assert payload["type"] == "error"
    assert payload["error_code"] == "DRIFT-3002"
    assert payload["category"] == "analysis"
    assert payload["exit_code"] == 3
    assert payload["message"] == "boom"
    assert payload["detail"].startswith("[DRIFT-3002]")
    assert payload["recoverable"] is False


def test_workers_zero_is_rejected_by_cli() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(cli.main, ["analyze", "--workers", "0", "-q"])

    assert result.exit_code != 0
    assert "0" in result.output
