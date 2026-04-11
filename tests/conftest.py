"""Shared fixtures for Drift tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Literal

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom CLI options for the test suite."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run tests marked as slow",
    )
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="regenerate golden snapshot files instead of comparing",
    )
    parser.addoption(
        "--save-findings",
        action="store_true",
        default=False,
        help="save smoke-test findings to benchmark_results/<repo>_full.json",
    )
    parser.addoption(
        "--smoke-profile",
        action="store",
        default="pr",
        choices=("pr", "nightly"),
        help="select external smoke repo profile (pr=fast, nightly=full)",
    )
    parser.addoption(
        "--refresh-smoke-cache",
        action="store_true",
        default=False,
        help="refresh cached external smoke repositories before analysis",
    )


def smoke_profile(config: pytest.Config) -> Literal["pr", "nightly"]:
    """Return the selected smoke profile."""
    return config.getoption("--smoke-profile", default="pr")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect slow tests unless the user opted in explicitly."""
    if config.getoption("--run-slow"):
        return

    markexpr = (getattr(config.option, "markexpr", "") or "").strip()
    if markexpr:
        return

    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("slow") is not None:
            deselected.append(item)
        else:
            kept.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure with Python files."""
    # Service layer
    svc = tmp_path / "services"
    svc.mkdir()
    (svc / "__init__.py").write_text("")
    (svc / "payment_service.py").write_text(
        textwrap.dedent("""\
        class PaymentError(Exception):
            pass

        def process_payment(amount: float, currency: str) -> dict:
            \"\"\"Process a payment transaction.\"\"\"
            try:
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                return {"status": "ok", "amount": amount}
            except ValueError as e:
                raise PaymentError(str(e)) from e

        def refund_payment(transaction_id: str) -> bool:
            try:
                # AI-generated: different error handling pattern
                result = lookup_transaction(transaction_id)
                return True
            except Exception as e:
                print(e)
                return False

        def lookup_transaction(tid: str) -> dict:
            return {"id": tid}
    """)
    )

    # API layer
    api = tmp_path / "api"
    api.mkdir()
    (api / "__init__.py").write_text("")
    (api / "routes.py").write_text(
        textwrap.dedent("""\
        from services.payment_service import process_payment
        from db.models import User

        def get_payments():
            return []

        def create_payment(data: dict):
            return process_payment(data["amount"], data["currency"])
    """)
    )

    # DB layer
    db = tmp_path / "db"
    db.mkdir()
    (db / "__init__.py").write_text("")
    (db / "models.py").write_text(
        textwrap.dedent("""\
        class User:
            pass

        class Payment:
            pass
    """)
    )

    # Utils
    utils = tmp_path / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("")
    (utils / "helpers.py").write_text(
        textwrap.dedent("""\
        def format_currency(amount: float, currency: str = "EUR") -> str:
            return f"{amount:.2f} {currency}"

        def format_money(value: float, cur: str = "EUR") -> str:
            \"\"\"Almost identical to format_currency — a near-duplicate.\"\"\"
            return f"{value:.2f} {cur}"
    """)
    )

    # Test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_payment.py").write_text(
        textwrap.dedent("""\
        def test_process_payment():
            assert True

        def test_refund_payment():
            assert True
    """)
    )

    return tmp_path


@pytest.fixture
def tmp_ts_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure with TypeScript files.

    Mirrors tmp_repo but uses TypeScript: services, API endpoints,
    models, utils, and a test file — suitable for multi-signal testing.
    """
    # Service layer
    svc = tmp_path / "services"
    svc.mkdir()
    (svc / "payment.service.ts").write_text(
        textwrap.dedent("""\
        export class PaymentError extends Error {
            constructor(message: string) {
                super(message);
                this.name = "PaymentError";
            }
        }

        export async function processPayment(
            amount: number,
            currency: string,
        ): Promise<{ status: string; amount: number }> {
            /** Process a payment transaction. */
            try {
                if (amount <= 0) {
                    throw new Error("Amount must be positive");
                }
                return { status: "ok", amount };
            } catch (e: unknown) {
                throw new PaymentError(String(e));
            }
        }

        export async function refundPayment(transactionId: string): Promise<boolean> {
            try {
                const result = await lookupTransaction(transactionId);
                return true;
            } catch (e) {
                console.error(e);
                return false;
            }
        }

        export function lookupTransaction(tid: string): Promise<{ id: string }> {
            return Promise.resolve({ id: tid });
        }
    """),
        encoding="utf-8",
    )

    # API layer (Express-style)
    api = tmp_path / "api"
    api.mkdir()
    (api / "routes.ts").write_text(
        textwrap.dedent("""\
        import { Router, Request, Response } from "express";
        import { processPayment } from "../services/payment.service";

        const router = Router();

        router.get("/payments", (req: Request, res: Response) => {
            res.json([]);
        });

        router.post("/payments", async (req: Request, res: Response) => {
            const result = await processPayment(req.body.amount, req.body.currency);
            res.json(result);
        });

        export default router;
    """),
        encoding="utf-8",
    )

    # Models
    models = tmp_path / "models"
    models.mkdir()
    (models / "user.ts").write_text(
        textwrap.dedent("""\
        export interface User {
            id: string;
            email: string;
            createdAt: Date;
        }

        export interface Payment {
            id: string;
            amount: number;
            currency: string;
            userId: string;
        }
    """),
        encoding="utf-8",
    )

    # Utils
    utils = tmp_path / "utils"
    utils.mkdir()
    (utils / "formatters.ts").write_text(
        textwrap.dedent("""\
        export function formatCurrency(amount: number, currency: string = "EUR"): string {
            return `${amount.toFixed(2)} ${currency}`;
        }

        export function formatMoney(value: number, cur: string = "EUR"): string {
            /** Almost identical to formatCurrency — a near-duplicate. */
            return `${value.toFixed(2)} ${cur}`;
        }
    """),
        encoding="utf-8",
    )

    # Test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "payment.spec.ts").write_text(
        textwrap.dedent("""\
        import { processPayment, refundPayment } from "../services/payment.service";

        describe("Payment", () => {
            it("should process payment", async () => {
                const result = await processPayment(100, "EUR");
                expect(result.status).toBe("ok");
            });

            it("should refund payment", async () => {
                const result = await refundPayment("tx-1");
                expect(result).toBe(true);
            });
        });
    """),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def sample_python_source() -> str:
    """A sample Python file with various patterns."""
    return textwrap.dedent("""\
        import os
        from pathlib import Path
        from typing import Optional

        class MyService:
            \"\"\"A sample service class.\"\"\"

            def __init__(self, name: str):
                self.name = name

            def process(self, data: dict) -> dict:
                try:
                    result = self._validate(data)
                    return {"status": "ok", "data": result}
                except ValueError as e:
                    raise ServiceError(str(e)) from e

            def _validate(self, data: dict) -> dict:
                if not data:
                    raise ValueError("Empty data")
                return data

            async def fetch_remote(self, url: str) -> bytes:
                try:
                    response = await client.get(url)
                    return response.content
                except Exception:
                    logger.error("Failed to fetch %s", url)
                    return b""

        class ServiceError(Exception):
            pass

        def standalone_function(x: int, y: int) -> int:
            \"\"\"Add two numbers.\"\"\"
            return x + y
    """)
