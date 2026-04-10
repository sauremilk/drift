"""Tests for TypeScript interface and type alias extraction (Task 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import parse_typescript_file, tree_sitter_available

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)

FIXTURES = Path(__file__).parent / "fixtures" / "typescript" / "interface_extraction"


@needs_tree_sitter
class TestInterfaceExtraction:
    """Test interface and type alias extraction from TypeScript files."""

    def test_basic_interface(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        ifaces = [c for c in result.classes if c.is_interface]
        names = {c.name for c in ifaces}

        assert "UserService" in names
        assert "Config" in names
        assert "UserId" in names
        assert "Result" in names

    def test_interface_is_interface_flag(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        for cls in result.classes:
            if cls.name in ("UserService", "Config", "UserId", "Result"):
                assert cls.is_interface is True, f"{cls.name} should be an interface"

    def test_interface_methods(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        user_svc = next(c for c in result.classes if c.name == "UserService")
        method_names = {m.name for m in user_svc.methods}

        assert "UserService.getUser" in method_names
        assert "UserService.updateUser" in method_names

    def test_interface_method_params(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        user_svc = next(c for c in result.classes if c.name == "UserService")
        get_user = next(m for m in user_svc.methods if "getUser" in m.name)

        assert "id" in get_user.parameters

    def test_interface_method_return_type(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        user_svc = next(c for c in result.classes if c.name == "UserService")
        get_user = next(m for m in user_svc.methods if "getUser" in m.name)

        assert get_user.return_type is not None
        assert "Promise" in get_user.return_type

    def test_type_alias_has_no_methods(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        user_id = next(c for c in result.classes if c.name == "UserId")

        assert user_id.is_interface is True
        assert user_id.methods == []

    def test_interface_extends(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/complex_interfaces.ts"),
            Path("."),
        )
        user_entity = next(c for c in result.classes if c.name == "UserEntity")

        assert user_entity.is_interface is True
        assert "BaseEntity" in user_entity.bases

    def test_generic_interface_methods(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/complex_interfaces.ts"),
            Path("."),
        )
        repo = next(c for c in result.classes if c.name == "Repository")

        assert repo.is_interface is True
        method_names = {m.name for m in repo.methods}
        assert "Repository.findById" in method_names
        assert "Repository.save" in method_names
        assert "Repository.delete" in method_names

    def test_empty_file_no_interfaces(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/empty.ts"),
            Path("."),
        )
        ifaces = [c for c in result.classes if c.is_interface]
        assert len(ifaces) == 0

    def test_regular_class_not_interface(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/empty.ts"),
            Path("."),
        )
        regular = [c for c in result.classes if not c.is_interface]
        assert any(c.name == "Regular" for c in regular)

    def test_interface_language_set(self) -> None:
        result = parse_typescript_file(
            Path("tests/fixtures/typescript/interface_extraction/user_service.ts"),
            Path("."),
        )
        for cls in result.classes:
            if cls.is_interface:
                assert cls.language == "typescript"

    def test_python_classinfo_default_not_interface(self) -> None:
        """Verify that the default ClassInfo is not marked as interface."""
        from drift.models import ClassInfo

        ci = ClassInfo(
            name="Foo",
            file_path=Path("foo.py"),
            start_line=1,
            end_line=10,
            language="python",
        )
        assert ci.is_interface is False
