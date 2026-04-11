"""MCP tool catalog — parameter introspection and metadata enrichment.

Extracted from ``mcp_server.py`` to separate catalog generation from
MCP tool registration and transport wiring.

Decision: ADR-022
"""

from __future__ import annotations

import functools
import inspect
import re as _re
from typing import Any


def _extract_param_descriptions(doc: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style Args: docstring section."""
    result: dict[str, str] = {}
    in_args = False
    current_param: str | None = None
    current_parts: list[str] = []
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if not in_args:
            continue
        if not stripped:
            continue
        # Non-indented non-empty line = section ended
        if not line.startswith("    ") and not line.startswith("\t"):
            break
        # New param: "name: description" at first indent level
        m = _re.match(r"^(\w+):\s*(.*)", stripped)
        if m:
            if current_param:
                result[current_param] = " ".join(current_parts).strip()
            current_param = m.group(1)
            current_parts = [m.group(2)] if m.group(2) else []
        elif current_param:
            current_parts.append(stripped)
    if current_param:
        result[current_param] = " ".join(current_parts).strip()
    return result


def _annotation_to_string(annotation: Any) -> str:
    """Resolve a Python type annotation to a JSON Schema type string.

    Properly unwraps ``Annotated[T, ...]`` and maps Python primitives to
    their JSON Schema equivalents.
    """
    import types as _bt
    import typing

    if annotation is inspect.Signature.empty:
        return "Any"
    if isinstance(annotation, str):
        return annotation

    # Unwrap Annotated[T, ...] → T
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        args = typing.get_args(annotation)
        if args:
            return _annotation_to_string(args[0])

    # Handle Union / Optional (T | None)
    if origin is _bt.UnionType or origin is typing.Union:
        args = typing.get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _annotation_to_string(non_none[0])

    # Map Python primitives to JSON Schema types
    json_type_map: dict[type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    if isinstance(annotation, type) and annotation in json_type_map:
        return json_type_map[annotation]

    name = getattr(annotation, "__name__", None)
    if isinstance(name, str):
        return name
    return str(annotation).replace("typing.", "")


def _field_description_from_annotation(annotation: Any) -> str | None:
    """Extract Field(description=...) from typing.Annotated metadata when present."""
    import typing

    if typing.get_origin(annotation) is not typing.Annotated:
        return None

    args = typing.get_args(annotation)
    for meta in args[1:]:
        description = getattr(meta, "description", None)
        if isinstance(description, str) and description.strip():
            return description.strip()
    return None


@functools.lru_cache(maxsize=1)
def get_tool_catalog() -> list[dict[str, Any]]:
    """Return MCP tool metadata for local inspection via CLI."""
    import typing

    from drift.mcp_server import _EXPORTED_MCP_TOOLS

    catalog: list[dict[str, Any]] = []

    for tool in _EXPORTED_MCP_TOOLS:
        signature = inspect.signature(tool)
        doc = inspect.getdoc(tool) or ""
        summary = doc.splitlines()[0] if doc else ""
        param_descs = _extract_param_descriptions(doc)

        # Resolve string annotations (from __future__ annotations) to real types
        try:
            resolved_hints = typing.get_type_hints(tool, include_extras=True)
        except Exception:
            resolved_hints = {}

        parameters: list[dict[str, Any]] = []
        for parameter in signature.parameters.values():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            annotation = resolved_hints.get(parameter.name, parameter.annotation)
            required = parameter.default is inspect.Signature.empty
            parameter_info: dict[str, Any] = {
                "name": parameter.name,
                "type": _annotation_to_string(annotation),
                "required": required,
            }
            if not required:
                parameter_info["default"] = parameter.default
            if parameter.name in param_descs:
                parameter_info["description"] = param_descs[parameter.name]
            else:
                field_desc = _field_description_from_annotation(annotation)
                if field_desc:
                    parameter_info["description"] = field_desc
            parameters.append(parameter_info)

        catalog.append(
            {
                "name": tool.__name__,
                "description": summary,
                "parameters": parameters,
            }
        )

    # Enrich catalog entries with cost metadata
    from drift.tool_metadata import TOOL_CATALOG, metadata_as_dict

    for entry in catalog:
        meta = TOOL_CATALOG.get(entry["name"])
        if meta is not None:
            entry["cost_metadata"] = metadata_as_dict(meta)

    return catalog
