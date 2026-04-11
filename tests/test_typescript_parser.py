"""Tests for TypeScript parser (tree-sitter) and regex fallback stub."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def ts_source() -> str:
    return textwrap.dedent("""\
        import { Router } from "express";
        import { UserService } from "./services/user";
        import type { Request, Response } from "express";

        interface User {
            id: string;
            name: string;
        }

        class UserController {
            private service: UserService;

            constructor(service: UserService) {
                this.service = service;
            }

            async getUser(req: Request, res: Response): Promise<void> {
                try {
                    const user = await this.service.findById(req.params.id);
                    res.json(user);
                } catch (error) {
                    console.error("Failed to get user", error);
                    res.status(500).json({ error: "Internal server error" });
                }
            }
        }

        const formatName = (first: string, last: string): string => {
            return `${first} ${last}`;
        };

        function processItems(items: string[]): number {
            let count = 0;
            for (const item of items) {
                if (item.length > 0) {
                    count++;
                }
            }
            return count;
        }

        export { UserController, formatName, processItems };
    """)


class TestTypeScriptParser:
    """Test the tree-sitter TypeScript parser (skipped if tree-sitter not installed)."""

    @pytest.fixture(autouse=True)
    def _skip_without_treesitter(self) -> None:
        from drift.ingestion.ts_parser import tree_sitter_available

        if not tree_sitter_available():
            pytest.skip("tree-sitter not installed")

    def test_parse_functions(self, tmp_path: Path, ts_source: str) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        (tmp_path / "app.ts").write_text(ts_source)
        result = parse_typescript_file(Path("app.ts"), tmp_path, "typescript")

        assert result.language == "typescript"
        assert len(result.functions) >= 3
        names = {f.name for f in result.functions}
        assert "formatName" in names
        assert "processItems" in names

    def test_extract_return_type_from_typed_arrow_declarator(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        ts_code = textwrap.dedent("""\
            const isUsableTimestamp: (input: unknown) => boolean = (input) => {
                return typeof input === "number" && input > 0;
            };
        """)
        (tmp_path / "typed_arrow.ts").write_text(ts_code, encoding="utf-8")
        result = parse_typescript_file(Path("typed_arrow.ts"), tmp_path, "typescript")

        fn = next((f for f in result.functions if f.name == "isUsableTimestamp"), None)
        assert fn is not None
        assert fn.return_type == "boolean"

    def test_extract_type_predicate_return_type(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        ts_code = textwrap.dedent("""\
            type BrowserNode = { kind: "browser" };

            export function isBrowserNode(node: unknown): node is BrowserNode {
                return typeof node === "object" && node !== null;
            }
        """)
        (tmp_path / "type_predicate.ts").write_text(ts_code, encoding="utf-8")
        result = parse_typescript_file(Path("type_predicate.ts"), tmp_path, "typescript")

        fn = next((f for f in result.functions if f.name == "isBrowserNode"), None)
        assert fn is not None
        assert fn.return_type == "node is BrowserNode"

    def test_parse_classes(self, tmp_path: Path, ts_source: str) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        (tmp_path / "app.ts").write_text(ts_source)
        result = parse_typescript_file(Path("app.ts"), tmp_path, "typescript")

        assert len(result.classes) >= 1
        cls_names = {c.name for c in result.classes}
        assert "UserController" in cls_names

    def test_parse_imports(self, tmp_path: Path, ts_source: str) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        (tmp_path / "app.ts").write_text(ts_source)
        result = parse_typescript_file(Path("app.ts"), tmp_path, "typescript")

        assert len(result.imports) >= 2
        modules = {imp.imported_module for imp in result.imports}
        assert "express" in modules or any("express" in m for m in modules)

    def test_parse_error_handling_patterns(self, tmp_path: Path, ts_source: str) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        (tmp_path / "app.ts").write_text(ts_source)
        result = parse_typescript_file(Path("app.ts"), tmp_path, "typescript")

        error_patterns = [p for p in result.patterns if p.category.value == "error_handling"]
        assert len(error_patterns) >= 1

    def test_api_client_wrapper_call_is_not_detected_as_endpoint(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        ts_code = textwrap.dedent("""\
            type DiscordReactOpts = { token?: string };

            function resolveDiscordRest(opts: DiscordReactOpts) {
                return {
                    put: async (_path: string, _payload: unknown) => undefined,
                };
            }

            export async function setChannelPermissionDiscord(
                payload: { channelId: string; targetId: string },
                opts: DiscordReactOpts = {},
            ) {
                const rest = resolveDiscordRest(opts);
                await rest.put(`/channels/${payload.channelId}/permissions/${payload.targetId}`, {
                    body: { type: "role" },
                });
                return { ok: true };
            }
        """)
        (tmp_path / "discord-client.ts").write_text(ts_code, encoding="utf-8")
        result = parse_typescript_file(Path("discord-client.ts"), tmp_path, "typescript")

        endpoint_patterns = [p for p in result.patterns if p.category.value == "api_endpoint"]
        assert endpoint_patterns == []

    def test_inline_route_handler_body_auth_is_detected(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        ts_code = textwrap.dedent("""\
            import express from "express";

            const app = express();

            function hasVerifiedBrowserAuth(req: unknown): boolean {
                return Boolean(req);
            }

            app.get("/sandbox/novnc", (req, res) => {
                if (!hasVerifiedBrowserAuth(req)) {
                    res.status(401).send("Unauthorized");
                    return;
                }
                res.send("ok");
            });
        """)
        (tmp_path / "bridge-server.ts").write_text(ts_code, encoding="utf-8")
        result = parse_typescript_file(Path("bridge-server.ts"), tmp_path, "typescript")

        endpoint_patterns = [p for p in result.patterns if p.category.value == "api_endpoint"]
        assert len(endpoint_patterns) == 1
        assert endpoint_patterns[0].fingerprint.get("has_auth") is True

    def test_enclosing_function_throw_auth_guard_is_detected(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        ts_code = textwrap.dedent("""\
            import express from "express";

            const router = express.Router();

            export async function startBrowserBridgeServer(options: {
                authToken?: string;
                authPassword?: string;
            }) {
                const { authToken, authPassword } = options;
                if (!authToken && !authPassword) {
                    throw new Error("bridge server requires auth token or password");
                }

                router.get("/bridge/status", (_req, res) => {
                    res.status(200).send("ok");
                });
            }
        """)
        (tmp_path / "bridge-server.ts").write_text(ts_code, encoding="utf-8")
        result = parse_typescript_file(Path("bridge-server.ts"), tmp_path, "typescript")

        endpoint_patterns = [p for p in result.patterns if p.category.value == "api_endpoint"]
        assert len(endpoint_patterns) == 1
        assert endpoint_patterns[0].function_name == "startBrowserBridgeServer"
        assert endpoint_patterns[0].fingerprint.get("has_auth") is True

    def test_parse_tsx(self, tmp_path: Path) -> None:
        from drift.ingestion.ts_parser import parse_typescript_file

        tsx_code = textwrap.dedent("""\
            import React from "react";

            interface Props {
                name: string;
            }

            const Greeting: React.FC<Props> = ({ name }) => {
                return <div>Hello, {name}!</div>;
            };

            export default Greeting;
        """)
        (tmp_path / "Greeting.tsx").write_text(tsx_code)
        result = parse_typescript_file(Path("Greeting.tsx"), tmp_path, "tsx")

        assert result.language == "tsx"
        assert result.line_count > 0


class TestTypeScriptFallback:
    """Test fallback to regex stub when tree-sitter is not installed."""

    def test_stub_extracts_imports(self, tmp_path: Path) -> None:
        from drift.ingestion.ast_parser import _parse_typescript_stub

        ts_code = textwrap.dedent("""\
            import { Router } from "express";
            import { UserService } from "./services/user";

            function hello() { return "world"; }
        """)
        (tmp_path / "app.ts").write_text(ts_code)
        result = _parse_typescript_stub(Path("app.ts"), tmp_path)

        assert result.language == "typescript"
        assert len(result.imports) >= 2

    def test_fallback_when_treesitter_missing(self, tmp_path: Path) -> None:
        ts_code = 'import { x } from "y";\n'
        (tmp_path / "app.ts").write_text(ts_code)

        with patch("drift.ingestion.ts_parser._ts_available", False):
            from drift.ingestion.ts_parser import parse_typescript_file

            result = parse_typescript_file(Path("app.ts"), tmp_path, "typescript")
            assert result.language == "typescript"
            assert len(result.imports) >= 1

    def test_fallback_preserves_requested_language(self, tmp_path: Path) -> None:
        tsx_code = 'import React from "react";\n'
        (tmp_path / "view.tsx").write_text(tsx_code)

        with patch("drift.ingestion.ts_parser._ts_available", False):
            from drift.ingestion.ts_parser import parse_typescript_file

            result = parse_typescript_file(Path("view.tsx"), tmp_path, "tsx")
            assert result.language == "tsx"
