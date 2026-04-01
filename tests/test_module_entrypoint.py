"""Tests for module entrypoint behavior (python -m drift)."""

from __future__ import annotations

import runpy


def test_module_entrypoint_uses_safe_main(monkeypatch) -> None:
    import drift.cli as cli

    called = {"safe_main": 0, "main": 0}

    def _safe_main() -> None:
        called["safe_main"] += 1

    def _main(*_args, **_kwargs) -> None:
        called["main"] += 1

    monkeypatch.setattr(cli, "safe_main", _safe_main)
    monkeypatch.setattr(cli, "main", _main)

    runpy.run_module("drift.__main__", run_name="__main__")

    assert called["safe_main"] == 1
    assert called["main"] == 0
