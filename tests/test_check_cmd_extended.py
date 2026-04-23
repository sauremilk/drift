"""Coverage-Boost: commands/check.py — _render_or_emit_output, _apply_baseline_filtering etc."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from drift.commands._shared import (
    apply_baseline_filtering as _apply_baseline_filtering,
)
from drift.commands._shared import (
    apply_signal_filtering as _apply_signal_filtering,
)
from drift.commands._shared import (
    render_or_emit_output as _render_or_emit_output,
)


def _make_analysis(findings=None):
    a = MagicMock()
    a.drift_score = 0.3
    a.findings = findings or []
    a.suppressed_count = 0
    return a


def _make_cfg():
    cfg = MagicMock()
    from drift.config import SignalWeights
    cfg.weights = SignalWeights()
    return cfg


# --------------------------------------------------------------------------
# _render_or_emit_output — sarif
# --------------------------------------------------------------------------

def test_render_sarif_calls_emit(tmp_path: Path) -> None:
    analysis = _make_analysis()
    with open(tmp_path / "out.txt", "w", encoding="utf-8") as fh:
        console = Console(file=fh)
        with patch(
            "drift.output.json_output.findings_to_sarif", return_value='{"sarif":"ok"}'
        ) as mock_sarif, patch(
            "drift.commands._shared._emit_machine_output"
        ) as mock_emit:
            _render_or_emit_output(
                analysis=analysis,
                output_format="sarif",
                compact_json=False,
                drift_score_scope="repo",
                output_file=None,
                effective_console=console,
                max_findings=20,
                no_code=False,
            )

    mock_sarif.assert_called_once_with(analysis)
    mock_emit.assert_called_once_with('{"sarif":"ok"}', None)


# --------------------------------------------------------------------------
# _render_or_emit_output — csv
# --------------------------------------------------------------------------

def test_render_csv_calls_emit(tmp_path: Path) -> None:
    analysis = _make_analysis()
    with open(tmp_path / "out.txt", "w", encoding="utf-8") as fh:
        console = Console(file=fh)
        with patch(
            "drift.output.csv_output.analysis_to_csv", return_value="col1,col2\n"
        ) as mock_csv, patch(
            "drift.commands._shared._emit_machine_output"
        ) as mock_emit:
            _render_or_emit_output(
                analysis=analysis,
                output_format="csv",
                compact_json=False,
                drift_score_scope="repo",
                output_file=None,
                effective_console=console,
                max_findings=20,
                no_code=False,
            )

    mock_csv.assert_called_once_with(analysis)
    mock_emit.assert_called_once_with("col1,col2\n", None)


# --------------------------------------------------------------------------
# _render_or_emit_output — agent-tasks
# --------------------------------------------------------------------------

def test_render_agent_tasks_calls_emit(tmp_path: Path) -> None:
    analysis = _make_analysis()
    with open(tmp_path / "out.txt", "w", encoding="utf-8") as fh:
        console = Console(file=fh)
        with patch(
            "drift.output.agent_tasks.analysis_to_agent_tasks_json", return_value="[]"
        ) as mock_at, patch(
            "drift.commands._shared._emit_machine_output"
        ) as mock_emit:
            _render_or_emit_output(
                analysis=analysis,
                output_format="agent-tasks",
                compact_json=False,
                drift_score_scope="repo",
                output_file=None,
                effective_console=console,
                max_findings=20,
                no_code=False,
            )

    mock_at.assert_called_once_with(analysis)
    mock_emit.assert_called_once_with("[]", None)


# --------------------------------------------------------------------------
# _render_or_emit_output — github
# --------------------------------------------------------------------------

def test_render_github_calls_emit(tmp_path: Path) -> None:
    analysis = _make_analysis()
    with open(tmp_path / "out.txt", "w", encoding="utf-8") as fh:
        console = Console(file=fh)
        with patch(
            "drift.output.github_format.findings_to_github_annotations", return_value="::notice::"
        ) as mock_gh, patch(
            "drift.commands._shared._emit_machine_output"
        ) as mock_emit:
            _render_or_emit_output(
                analysis=analysis,
                output_format="github",
                compact_json=False,
                drift_score_scope="repo",
                output_file=None,
                effective_console=console,
                max_findings=20,
                no_code=False,
            )

    mock_gh.assert_called_once_with(analysis)
    mock_emit.assert_called_once_with("::notice::", None)


# --------------------------------------------------------------------------
# _render_or_emit_output — llm
# --------------------------------------------------------------------------


def test_render_llm_passes_max_findings(tmp_path: Path) -> None:
    analysis = _make_analysis()
    with open(tmp_path / "out.txt", "w", encoding="utf-8") as fh:
        console = Console(file=fh)
        with (
            patch(
                "drift.output.llm_output.analysis_to_llm", return_value="llm"
            ) as mock_llm,
            patch(
                "drift.commands._shared._emit_machine_output"
            ) as mock_emit,
            pytest.warns(DeprecationWarning, match=r"--format llm is deprecated"),
        ):
            _render_or_emit_output(
                analysis=analysis,
                output_format="llm",
                compact_json=False,
                drift_score_scope="repo",
                output_file=None,
                effective_console=console,
                max_findings=7,
                no_code=False,
            )

    mock_llm.assert_called_once_with(analysis, max_findings=7)
    mock_emit.assert_called_once_with("llm", None)


# --------------------------------------------------------------------------
# _apply_baseline_filtering — with baseline_file
# --------------------------------------------------------------------------

def test_apply_baseline_filtering_updates_suppressed(tmp_path: Path) -> None:
    f1, f2, f3 = MagicMock(), MagicMock(), MagicMock()
    analysis = _make_analysis(findings=[f1, f2, f3])
    cfg = _make_cfg()
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")

    with patch("drift.baseline.load_baseline", return_value=set()), patch(
        "drift.baseline.baseline_diff", return_value=([f1], [f2, f3])
    ), patch("drift.commands._shared.recompute_analysis_summary"):
        _apply_baseline_filtering(analysis, cfg, baseline_file=baseline)

    assert analysis.findings == [f1]
    assert analysis.suppressed_count == 2


# --------------------------------------------------------------------------
# _apply_baseline_filtering — None (no-op)
# --------------------------------------------------------------------------

def test_apply_baseline_filtering_skips_when_none() -> None:
    analysis = _make_analysis(findings=["f1"])
    cfg = _make_cfg()
    _apply_baseline_filtering(analysis, cfg, baseline_file=None)
    assert analysis.findings == ["f1"]


# --------------------------------------------------------------------------
# _apply_signal_filtering — with select_signals
# --------------------------------------------------------------------------

def test_apply_signal_filtering_no_op_without_signals() -> None:
    analysis = _make_analysis(findings=["f1", "f2"])
    cfg = _make_cfg()
    _apply_signal_filtering(analysis, cfg, select_signals=None, ignore_signals=None)
    assert analysis.findings == ["f1", "f2"]


def test_apply_signal_filtering_filters_findings() -> None:
    from drift.models import SignalType
    f1 = MagicMock()
    f1.signal_type = SignalType("pattern_fragmentation")
    f2 = MagicMock()
    f2.signal_type = "unknown_xyz"
    analysis = _make_analysis(findings=[f1, f2])
    cfg = _make_cfg()
    with patch("drift.commands._shared.recompute_analysis_summary") as mock_recompute:
        _apply_signal_filtering(analysis, cfg, select_signals="PFS", ignore_signals=None)
    mock_recompute.assert_called_once()
