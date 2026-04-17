"""Regression tests for Issue #497 around drift_nudge docstring Args coverage."""

from __future__ import annotations


class TestIssue497DriftNudgeDocstringArgs:
    def test_drift_nudge_args_section_lists_repair_template_fields(self) -> None:
        from drift import mcp_catalog, mcp_server

        doc = mcp_server.drift_nudge.__doc__ or ""
        args = mcp_catalog._extract_param_descriptions(doc)

        assert "task_signal" in args
        assert "task_edit_kind" in args
        assert "task_context_class" in args
