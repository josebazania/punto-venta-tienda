from __future__ import annotations

import unittest

from pos import config
from pos.services.errors import ConflictError, ValidationError
from tests.base import ServiceTestCase


class CashServiceTests(ServiceTestCase):
    def test_open_cash_sets_expected_to_opening_amount(self) -> None:
        summary = self.open_cash(15000)
        self.assertEqual(summary["status"], config.SESSION_OPEN)
        self.assertEqual(summary["opening_cash_cents"], 15000)
        self.assertEqual(summary["expected_cash_cents"], 15000)
        self.assertEqual(self.ctx.cash.current()["id"], summary["id"])

    def test_only_one_open_cash_session(self) -> None:
        self.open_cash()
        with self.assertRaises(ConflictError):
            self.open_cash()

    def test_manual_movements_change_expected_cash(self) -> None:
        self.open_cash(10000)
        self.ctx.cash.add_movement("ingreso", 2500, "Fondo adicional")
        summary = self.ctx.cash.add_movement("egreso", 700, "Compra de bolsas")
        self.assertEqual(summary["income_cents"], 2500)
        self.assertEqual(summary["expense_cents"], 700)
        self.assertEqual(summary["expected_cash_cents"], 11800)
        movements = self.ctx.cash.movements(summary["id"])
        self.assertEqual(len(movements), 2)

    def test_movement_requires_open_session_and_valid_data(self) -> None:
        with self.assertRaises(ConflictError):
            self.ctx.cash.add_movement("ingreso", 100, "Sin caja")
        self.open_cash()
        with self.assertRaises(ValidationError):
            self.ctx.cash.add_movement("ingreso", 0, "Monto cero")
        with self.assertRaises(ValidationError):
            self.ctx.cash.add_movement("otro", 100, "Tipo inválido")
        with self.assertRaises(ValidationError):
            self.ctx.cash.add_movement("ingreso", 100, "x")

    def test_close_cash_records_difference_and_history(self) -> None:
        self.open_cash(10000)
        self.ctx.cash.add_movement("ingreso", 500, "Venta de bolsas")
        closed = self.ctx.cash.close(10400, "Faltante de 100")
        self.assertEqual(closed["status"], config.SESSION_CLOSED)
        self.assertEqual(closed["expected_cash_cents"], 10500)
        self.assertEqual(closed["counted_cash_cents"], 10400)
        self.assertEqual(closed["difference_cents"], -100)
        self.assertIsNone(self.ctx.cash.current())
        history = self.ctx.cash.history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], closed["id"])

    def test_close_without_open_session_fails(self) -> None:
        with self.assertRaises(ConflictError):
            self.ctx.cash.close(0)

    def test_can_open_new_session_after_closing(self) -> None:
        self.open_cash(5000)
        self.ctx.cash.close(5000)
        new_session = self.open_cash(2000)
        self.assertEqual(new_session["status"], config.SESSION_OPEN)
        self.assertEqual(len(self.ctx.cash.history()), 2)

    def test_invalid_opening_amount(self) -> None:
        with self.assertRaises(ValidationError):
            self.ctx.cash.open(-1)
        with self.assertRaises(ValidationError):
            self.ctx.cash.close(-1)

    def test_expected_cash_includes_sales_with_discount(self) -> None:
        product_id = self.make_product(price_cents=500, stock=10)
        self.open_cash(10000)
        self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 2}],
            discount_cents=100,
            payment_method="efectivo",
            cash_received_cents=2000,
        )
        summary = self.ctx.cash.current()
        self.assertEqual(summary["total_sales_cents"], 900)
        self.assertEqual(summary["expected_cash_cents"], 10900)


if __name__ == "__main__":
    unittest.main()
