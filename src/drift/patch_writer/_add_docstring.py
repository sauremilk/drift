"""AddDocstringWriter — inserts stub docstrings via libcst (ADR-076).

Supports Python functions and async functions only (v1 scope).
Requires ``drift[autopatch]`` (libcst >= 1.0).
"""

from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

from drift.fix_intent import EDIT_KIND_ADD_DOCSTRING
from drift.patch_writer._base import PatchResult, PatchResultStatus, PatchWriter
from drift.patch_writer.shared import _require_libcst

if TYPE_CHECKING:
    from drift.models import Finding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# libcst transformer
# ---------------------------------------------------------------------------


def _build_docstring_node(symbol: str) -> object:
    """Build a libcst SimpleStatementLine containing a docstring expression."""
    import libcst as cst

    docstring_text = f'"""TODO: document {symbol}."""'
    return cst.SimpleStatementLine(
        body=[
            cst.Expr(
                value=cst.SimpleString(docstring_text),
            )
        ],
    )


class _DocstringInserter:
    """libcst-based transformer that inserts a stub docstring into a target function."""

    def __init__(self, symbol: str, target_line: int) -> None:
        self._symbol = symbol
        self._target_line = target_line
        self._inserted = False

    def _func_matches(self, node: object, metadata: object = None) -> bool:
        """Return True when *node* is the function we want to patch."""
        import libcst as cst

        if not isinstance(node, (cst.FunctionDef,)):
            return False
        return node.name.value == self._symbol

    def _already_has_docstring(self, func_node: object) -> bool:
        """Return True when the function body starts with a string expression."""
        import libcst as cst

        body = getattr(func_node, "body", None)
        if body is None:
            return False
        stmts = getattr(body, "body", ())
        if not stmts:
            return False
        first = stmts[0]
        if isinstance(first, cst.SimpleStatementLine):
            for item in first.body:
                if isinstance(item, cst.Expr) and isinstance(
                    item.value, (cst.SimpleString, cst.FormattedString, cst.ConcatenatedString)
                ):
                    return True
        return False

    def transform(self, tree: object) -> tuple[object, bool]:
        """Return (new_tree, was_modified)."""
        import libcst as cst

        target_symbol = self._symbol

        class _Visitor(cst.CSTTransformer):
            found: bool = False
            skipped: bool = False

            def leave_FunctionDef(  # noqa: N802
                self_inner, original_node: cst.FunctionDef, updated_node: cst.FunctionDef  # noqa: N805
            ) -> cst.FunctionDef:
                if original_node.name.value != target_symbol:
                    return updated_node

                # Check if docstring already present
                body = updated_node.body
                stmts = list(body.body)
                if stmts:
                    first = stmts[0]
                    if isinstance(first, cst.SimpleStatementLine):
                        for item in first.body:
                            if isinstance(
                                item,
                                cst.Expr,
                            ) and isinstance(
                                item.value,
                                (cst.SimpleString, cst.FormattedString, cst.ConcatenatedString),
                            ):
                                self_inner.skipped = True
                                return updated_node

                # Insert docstring as first statement
                docstring_node = _build_docstring_node(target_symbol)
                new_body = cst.IndentedBlock(
                    body=[docstring_node, *stmts],
                    indent=body.indent,
                    header=body.header,
                    footer=body.footer,
                )
                self_inner.found = True
                return updated_node.with_changes(body=new_body)

        visitor = _Visitor()
        new_tree = tree.visit(visitor)  # type: ignore[union-attr]
        return new_tree, visitor.found and not visitor.skipped, visitor.skipped  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PatchWriter implementation
# ---------------------------------------------------------------------------


class AddDocstringWriter(PatchWriter):
    """Inserts a stub docstring into a Python function that lacks one."""

    @property
    def edit_kind(self) -> str:
        return EDIT_KIND_ADD_DOCSTRING

    def can_write(self, finding: Finding) -> bool:
        if finding.language != "python":
            return False
        return bool(finding.symbol)

    def generate_patch(self, finding: Finding, source: str) -> PatchResult:  # noqa: E501  # drift:ignore MDS
        """Generate a patch that inserts a docstring into the function identified by *finding*."""
        if finding.language != "python":
            return PatchResult(
                status=PatchResultStatus.UNSUPPORTED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=f"Language {finding.language!r} is not supported (Python only in v1)",
            )

        if not finding.symbol:
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason="finding.symbol is required for docstring insertion",
            )

        try:
            _require_libcst()
        except ImportError as exc:
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=str(exc),
            )

        try:
            import libcst as cst

            tree = cst.parse_module(source)
        except Exception as exc:
            logger.debug("AddDocstringWriter: parse failed: %s", exc)
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=f"libcst parse error: {exc}",
            )

        inserter = _DocstringInserter(
            symbol=finding.symbol,
            target_line=finding.start_line or 1,
        )

        try:
            result_tuple = inserter.transform(tree)
            new_tree, was_modified, was_skipped = result_tuple  # type: ignore[misc]
        except Exception as exc:
            logger.debug("AddDocstringWriter: transform failed: %s", exc)
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=f"libcst transform error: {exc}",
            )

        if was_skipped:
            return PatchResult(
                status=PatchResultStatus.SKIPPED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                original_source=source,
                reason="Function already has a docstring",
            )

        if not was_modified:
            return PatchResult(
                status=PatchResultStatus.SKIPPED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                original_source=source,
                reason=f"Function {finding.symbol!r} not found in source",
            )

        patched = new_tree.code  # type: ignore[union-attr]

        diff = "".join(
            difflib.unified_diff(
                source.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=str(finding.file_path or "original"),
                tofile=str(finding.file_path or "patched"),
            )
        )

        return PatchResult(
            status=PatchResultStatus.GENERATED,
            edit_kind=self.edit_kind,
            file_path=finding.file_path,
            diff=diff,
            patched_source=patched,
            original_source=source,
        )
