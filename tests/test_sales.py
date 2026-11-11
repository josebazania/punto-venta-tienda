from __future__ import annotations

import unittest

from pos import config
from pos.services.errors import ConflictError, ValidationError
from tests.base import ServiceTestCase


class SaleServiceTests(ServiceTestCase):
    def test_cash_checkout_with_discount_updates_stock_and_cash(self) -> None:
        product_id = self.make_product(price_cents=500, stock=10)
        self.open_cash(10000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 2}],
            discount_cents=100,
            payment_method="efectivo",
            cash_received_cents=2000,
        )
        self.assertRegex(sale["folio"], r"^V-\d{8}-\d{4}$")
        self.assertEqual(sale["subtotal_cents"], 1000)
        self.assertEqual(sale["discount_cents"], 100)
        self.assertEqual(sale["total_cents"], 900)
        self.assertEqual(sale["cash_received_cents"], 2000)
        self.assertEqual(sale["change_cents"], 1100)
        self.assertEqual(sale["status"], config.SALE_COMPLETED)
        self.assertEqual(len(sale["items"]), 1)
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 8)
        self.assertEqual(self.ctx.cash.current()["expected_cash_cents"], 10900)
        movement = self.ctx.inventory.list_movements(product_id=product_id)[0]
        self.assertEqual(movement["kind"], "venta")
        self.assertEqual(movement["quantity_delta"], -2)
        self.assertEqual(movement["stock_after"], 8)

    def test_card_payment_does_not_affect_cash_expected(self) -> None:
        product_id = self.make_product(price_cents=750)
        self.open_cash(5000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="tarjeta",
            cash_received_cents=0,
        )
        self.assertEqual(sale["total_cents"], 750)
        self.assertEqual(sale["cash_received_cents"], 0)
        self.assertEqual(sale["change_cents"], 0)
        summary = self.ctx.cash.current()
        self.assertEqual(summary["cash_sales_cents"], 0)
        self.assertEqual(summary["card_sales_cents"], 750)
        self.assertEqual(summary["expected_cash_cents"], 5000)

    def test_yape_sale_is_counted_without_affecting_cash(self) -> None:
        from pos.receipt import build_receipt_text
        product_id = self.make_product(price_cents=750)
        self.open_cash(5000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}], payment_method="yape"
        )
        summary = self.ctx.cash.current()
        self.assertEqual(sale["payment_method"], "yape")
        self.assertEqual(summary["yape_sales_cents"], 750)
        self.assertEqual(summary["total_sales_cents"], 750)
        self.assertEqual(summary["expected_cash_cents"], 5000)
        self.assertEqual(self.ctx.reports.today()["yape_cents"], 750)
        self.assertIn("Yape", build_receipt_text(sale, self.ctx.settings.get_store_info()))
        self.ctx.sales.cancel(sale["id"], "Cancelada")
        self.assertEqual(self.ctx.cash.current()["yape_sales_cents"], 0)
        self.assertEqual(self.ctx.cash.current()["expected_cash_cents"], 5000)

    def test_statistics_exclude_cancelled_sales(self) -> None:
        from datetime import datetime
        product_id = self.make_product(price_cents=500, stock=10)
        self.open_cash()
        self.ctx.sales.checkout([{"product_id": product_id, "quantity": 2}], payment_method="yape")
        cancelled = self.ctx.sales.checkout([{"product_id": product_id, "quantity": 1}], payment_method="tarjeta")
        self.ctx.sales.cancel(cancelled["id"], "Prueba")
        today = datetime.now().date().isoformat()
        report = self.ctx.reports.statistics(today, today)
        self.assertEqual((report["count"], report["total"]), (1, 1000))
        self.assertEqual(report["payments"][0]["method"], "yape")
        self.assertEqual(report["products"][0]["quantity"], 2)
        self.assertEqual(report["daily"][0]["total"], 1000)

    def test_checkout_requires_open_cash_session(self) -> None:
        product_id = self.make_product()
        with self.assertRaises(ConflictError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 1}],
                payment_method="efectivo",
                cash_received_cents=500,
            )
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 10)

    def test_checkout_rejects_insufficient_stock_without_partial_changes(self) -> None:
        product_id = self.make_product(stock=1)
        self.open_cash()
        with self.assertRaises(ConflictError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 2}],
                payment_method="efectivo",
                cash_received_cents=1000,
            )
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 1)
        self.assertEqual(self.ctx.sales.list(), [])
        self.assertEqual(len(self.ctx.inventory.list_movements(product_id=product_id)), 1)

    def test_checkout_rejects_inactive_product(self) -> None:
        product_id = self.make_product(active=False)
        self.open_cash()
        with self.assertRaises(ConflictError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 1}],
                payment_method="efectivo",
                cash_received_cents=500,
            )

    def test_checkout_rejects_discount_above_subtotal(self) -> None:
        product_id = self.make_product(price_cents=500)
        self.open_cash()
        with self.assertRaises(ValidationError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 1}],
                discount_cents=501,
                payment_method="efectivo",
                cash_received_cents=500,
            )

    def test_checkout_rejects_insufficient_cash(self) -> None:
        product_id = self.make_product(price_cents=500)
        self.open_cash()
        with self.assertRaises(ValidationError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 1}],
                payment_method="efectivo",
                cash_received_cents=499,
            )

    def test_decimal_quantity_for_bulk_product(self) -> None:
        product_id = self.make_product(
            name="Tomate", price_cents=800, stock=10, unit="kg"
        )
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 0.25}],
            payment_method="efectivo",
            cash_received_cents=200,
        )
        self.assertEqual(sale["total_cents"], 200)
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 9.75)

    def test_quantities_are_merged_and_limited_to_three_decimals(self) -> None:
        product_id = self.make_product(stock=10)
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [
                {"product_id": product_id, "quantity": 1},
                {"product_id": product_id, "quantity": 2},
            ],
            payment_method="efectivo",
            cash_received_cents=1500,
        )
        self.assertEqual(len(sale["items"]), 1)
        self.assertEqual(sale["items"][0]["quantity"], 3)
        with self.assertRaises(ValidationError):
            self.ctx.sales.checkout(
                [{"product_id": product_id, "quantity": 0.0001}],
                payment_method="efectivo",
                cash_received_cents=100,
            )
        with self.assertRaises(ValidationError):
            self.ctx.sales.checkout([], payment_method="efectivo")

    def test_folios_increment_within_the_day(self) -> None:
        product_id = self.make_product(price_cents=100, stock=10)
        self.open_cash()
        first = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=100,
        )
        second = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=100,
        )
        first_number = int(first["folio"].rsplit("-", 1)[1])
        second_number = int(second["folio"].rsplit("-", 1)[1])
        self.assertEqual(second_number, first_number + 1)

    def test_cancel_same_session_restores_stock_and_expected_cash(self) -> None:
        product_id = self.make_product(price_cents=500, stock=10)
        self.open_cash(10000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 2}],
            payment_method="efectivo",
            cash_received_cents=1000,
        )
        self.assertEqual(self.ctx.cash.current()["expected_cash_cents"], 11000)
        cancelled = self.ctx.sales.cancel(sale["id"], "Cliente devolvió el producto")
        self.assertEqual(cancelled["status"], config.SALE_CANCELLED)
        self.assertEqual(cancelled["cancel_reason"], "Cliente devolvió el producto")
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 10)
        summary = self.ctx.cash.current()
        self.assertEqual(summary["expected_cash_cents"], 10000)
        self.assertEqual(summary["refund_cents"], 0)
        movement = self.ctx.inventory.list_movements(product_id=product_id)[0]
        self.assertEqual(movement["kind"], "cancelacion")
        self.assertEqual(movement["quantity_delta"], 2)

    def test_cannot_cancel_twice(self) -> None:
        product_id = self.make_product()
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=500,
        )
        self.ctx.sales.cancel(sale["id"], "Primera anulación")
        with self.assertRaises(ConflictError):
            self.ctx.sales.cancel(sale["id"], "Segunda anulación")
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 10)

    def test_cancel_sale_from_closed_session_creates_refund_in_current_cash(self) -> None:
        product_id = self.make_product(price_cents=500, stock=10)
        self.open_cash(10000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=500,
        )
        self.ctx.cash.close(10500, "Cierre correcto")
        self.open_cash(1000)
        self.ctx.sales.cancel(sale["id"], "Devolución posterior")
        summary = self.ctx.cash.current()
        self.assertEqual(summary["refund_cents"], 500)
        self.assertEqual(summary["expected_cash_cents"], 500)
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 10)
        movements = self.ctx.cash.movements(summary["id"])
        self.assertEqual(movements[0]["kind"], "devolucion")
        self.assertEqual(movements[0]["sale_id"], sale["id"])

    def test_cancel_cash_sale_requires_open_cash_for_refund(self) -> None:
        product_id = self.make_product(price_cents=500)
        self.open_cash(10000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=500,
        )
        self.ctx.cash.close(10500)
        with self.assertRaises(ConflictError):
            self.ctx.sales.cancel(sale["id"], "Sin caja abierta")
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 9)
        self.assertEqual(self.ctx.sales.get(sale["id"])["status"], config.SALE_COMPLETED)

    def test_cancel_card_sale_does_not_require_open_cash(self) -> None:
        product_id = self.make_product(price_cents=500)
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="tarjeta",
        )
        self.ctx.cash.close(10000)
        cancelled = self.ctx.sales.cancel(sale["id"], "Anulación con tarjeta")
        self.assertEqual(cancelled["status"], config.SALE_CANCELLED)
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 10)

    def test_cancel_requires_reason(self) -> None:
        product_id = self.make_product()
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=500,
        )
        with self.assertRaises(ValidationError):
            self.ctx.sales.cancel(sale["id"], "  x ")

    def test_sale_list_filters_and_search(self) -> None:
        product_id = self.make_product(name="Aceite vegetal", price_cents=900)
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=900,
        )
        self.assertEqual(len(self.ctx.sales.list(search="Aceite")), 1)
        self.assertEqual(len(self.ctx.sales.list(search=sale["folio"])), 1)
        self.assertEqual(self.ctx.sales.list(search="Inexistente"), [])
        self.assertEqual(
            len(self.ctx.sales.list(status=config.SALE_CANCELLED)), 0
        )


if __name__ == "__main__":
    unittest.main()
