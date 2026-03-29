"""Runtime tests for top-level CLI error handling in ``safe_main``."""

from __future__ import annotations

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

    assert exc_info.value.code == 2
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

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "DRIFT-2003" in captured.err
    assert "Hint: run with -v for the full traceback." in captured.err


def test_safe_main_click_exception_is_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", _raise(click.ClickException("invalid")))

    with pytest.raises(click.ClickException):
        cli.safe_main()


def test_safe_main_exit_is_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", _raise(click.exceptions.Exit(2)))

    with pytest.raises(click.exceptions.Exit):
        cli.safe_main()
