"""AddGuardClauseWriter — inserts None-guard clauses via libcst (ADR-076).

Supports Python functions only (v1 scope).
Requires ``drift[autopatch]`` (libcst >= 1.0).

For each parameter name listed in ``finding.metadata["guard_params"]``,
inserts at the start of the function body::

    if <param> is None:
        raise TypeError("<param> must not be None")

Parameters that already have a guard clause are skipped (idempotent).
"""

from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

from drift.fix_intent import EDIT_KIND_ADD_GUARD_CLAUSE
from drift.patch_writer._base import PatchResult, PatchResultStatus, PatchWriter
from drift.patch_writer.shared import _require_libcst

if TYPE_CHECKING:
    from drift.models import Finding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: detect existing guard for a parameter
# ---------------------------------------------------------------------------


def _param_has_guard(stmts: list, param: str) -> bool:
    """Return True if any statement in *stmts* is a None-guard for *param*.

    Matches patterns::

        if param is None: raise ...
        if param is None:
            raise ...
    """
    try:
        import libcst as cst
    except ImportError:
        return False

    for stmt in stmts:
        if not isinstance(stmt, cst.If):
            continue
        test = stmt.test
        if not isinstance(test, cst.Comparison):
            continue
        comparisons = test.comparisons
        if not comparisons:
            continue
        first_comp = comparisons[0]
        if not isinstance(first_comp.operator, cst.Is):
            continue
        if not isinstance(first_comp.comparator, cst.Name):
            continue
        if first_comp.comparator.value != "None":
            continue
        # Check left side is the param name
        if isinstance(test.left, cst.Name) and test.left.value == param:
            return True
    return False


# ---------------------------------------------------------------------------
# Helper: build a guard if-statement
# ---------------------------------------------------------------------------


def _build_guard_stmt(param: str) -> object:
    """Build ``if <param> is None: raise TypeError('<param> must not be None')``."""
    import libcst as cst

    raise_stmt = cst.Raise(
        exc=cst.Call(
            func=cst.Name("TypeError"),
            args=[
                cst.Arg(
                    value=cst.SimpleString(f'"{param} must not be None"')
                )
            ],
        )
    )
    return cst.If(
        test=cst.Comparison(
            left=cst.Name(param),
            comparisons=[
                cst.ComparisonTarget(
                    operator=cst.Is(),
                    comparator=cst.Name("None"),
                )
            ],
        ),
        body=cst.IndentedBlock(
            body=[cst.SimpleStatementLine(body=[raise_stmt])]
        ),
    )


# ---------------------------------------------------------------------------
# libcst transformer
# ---------------------------------------------------------------------------


class _GuardInserter:
    """libcst transformer that prepends None-guards for the specified params."""

    def __init__(self, symbol: str, guard_params: list[str]) -> None:
        self._symbol = symbol
        self._guard_params = guard_params

    def transform(self, tree: object) -> tuple[object, bool, bool]:
        """Return (new_tree, was_modified, was_fully_skipped)."""
        import libcst as cst

        target_symbol = self._symbol
        guard_params = self._guard_params

        class _Visitor(cst.CSTTransformer):
            inserted_count: int = 0
            skipped_count: int = 0

            def leave_FunctionDef(  # noqa: N802
                self_inner, original_node: cst.FunctionDef, updated_node: cst.FunctionDef  # noqa: N805
            ) -> cst.FunctionDef:
                if original_node.name.value != target_symbol:
                    return updated_node

                body = updated_node.body
                existing_stmts = list(body.body)

                guards_to_insert: list[object] = []
                for param in guard_params:
                    if _param_has_guard(existing_stmts, param):
                        self_inner.skipped_count += 1
                        continue
                    guards_to_insert.append(_build_guard_stmt(param))
                    self_inner.inserted_count += 1

                if not guards_to_insert:
                    return updated_node

                # Find the split point: insert new guards after any existing
                # guard-like if-statements at the start of the function body,
                # so the insertion order is deterministic and readable.
                insert_at = 0
                for stmt in existing_stmts:
                    if isinstance(stmt, cst.If):
                        insert_at += 1
                    else:
                        break

                merged = [
                    *existing_stmts[:insert_at],
                    *guards_to_insert,
                    *existing_stmts[insert_at:],
                ]
                new_body = cst.IndentedBlock(
                    body=merged,
                    indent=body.indent,
                    header=body.header,
                    footer=body.footer,
                )
                return updated_node.with_changes(body=new_body)

        visitor = _Visitor()
        new_tree = tree.visit(visitor)  # type: ignore[union-attr]

        was_modified = visitor.inserted_count > 0
        all_skipped = visitor.skipped_count == len(guard_params) and visitor.inserted_count == 0
        return new_tree, was_modified, all_skipped


# ---------------------------------------------------------------------------
# PatchWriter implementation
# ---------------------------------------------------------------------------


class AddGuardClauseWriter(PatchWriter):
    """Prepends None-guard clauses to a Python function's parameter list."""

    @property
    def edit_kind(self) -> str:
        return EDIT_KIND_ADD_GUARD_CLAUSE

    def can_write(self, finding: Finding) -> bool:
        if finding.language != "python":
            return False
        if not finding.symbol:
            return False
        guard_params = finding.metadata.get("guard_params") or []
        return bool(guard_params)

    def generate_patch(  # drift:ignore MDS
        self, finding: Finding, source: str
    ) -> PatchResult:
        """Generate a patch inserting None-guard clauses into the function from *finding*."""
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
                reason="finding.symbol is required for guard clause insertion",
            )

        guard_params: list[str] = list(finding.metadata.get("guard_params") or [])
        if not guard_params:
            return PatchResult(
                status=PatchResultStatus.SKIPPED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason="No guard_params in finding.metadata",
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
            logger.debug("AddGuardClauseWriter: parse failed: %s", exc)
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=f"libcst parse error: {exc}",
            )

        inserter = _GuardInserter(
            symbol=finding.symbol,
            guard_params=guard_params,
        )

        try:
            new_tree, was_modified, all_skipped = inserter.transform(tree)
        except Exception as exc:
            logger.debug("AddGuardClauseWriter: transform failed: %s", exc)
            return PatchResult(
                status=PatchResultStatus.FAILED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                reason=f"libcst transform error: {exc}",
            )

        if all_skipped:
            return PatchResult(
                status=PatchResultStatus.SKIPPED,
                edit_kind=self.edit_kind,
                file_path=finding.file_path,
                original_source=source,
                reason="All specified parameters already have guard clauses",
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
