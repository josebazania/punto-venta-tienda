from __future__ import annotations

import unittest

from pos import config
from pos.receipt import build_receipt_text
from tests.base import ServiceTestCase


class ReceiptTests(ServiceTestCase):
    def test_receipt_contains_store_sale_and_payment_data(self) -> None:
        product_id = self.make_product(name="Café pasado 250 g", price_cents=1250)
        self.open_cash(5000)
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 2}],
            discount_cents=100,
            payment_method="efectivo",
            cash_received_cents=5000,
        )
        store = {
            "business_name": "Bodega Central",
            "ruc": "20111222333",
            "address": "Calle Los Olivos 456",
            "phone": "999 111 222",
            "receipt_footer": "Gracias por preferirnos",
        }
        text = build_receipt_text(sale, store)
        self.assertIn("Bodega Central", text)
        self.assertIn(sale["folio"], text)
        self.assertIn("Café pasado 250 g", text)
        self.assertIn(config.money(sale["total_cents"]), text)
        self.assertIn("Efectivo recibido", text)
        self.assertIn("Vuelto", text)
        self.assertIn("Gracias por preferirnos", text)
        self.assertTrue(all(len(line) <= 48 for line in text.splitlines()))

    def test_receipt_omits_cash_lines_for_card_payment(self) -> None:
        product_id = self.make_product(price_cents=300)
        self.open_cash()
        sale = self.ctx.sales.checkout(
            [{"product_id": product_id, "quantity": 1}],
            payment_method="tarjeta",
        )
        text = build_receipt_text(
            sale,
            {
                "business_name": "Tienda",
                "ruc": "",
                "address": "",
                "phone": "",
                "receipt_footer": "",
            },
        )
        self.assertIn("Tarjeta", text)
        self.assertNotIn("Efectivo recibido", text)


if __name__ == "__main__":
    unittest.main()
