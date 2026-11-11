from __future__ import annotations

import unittest

from pos.services.errors import ConflictError, ValidationError
from tests.base import ServiceTestCase


class ProductServiceTests(ServiceTestCase):
    def test_create_generates_sku_and_initial_stock_movement(self) -> None:
        product_id = self.make_product(stock=12.5)
        product = self.ctx.products.get(product_id)
        self.assertRegex(product["sku"], r"^P\d{4}$")
        self.assertEqual(product["stock"], 12.5)
        self.assertEqual(product["category_name"], "Abarrotes")
        movements = self.ctx.inventory.list_movements(product_id=product_id)
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["kind"], "inicial")
        self.assertEqual(movements[0]["quantity_delta"], 12.5)

    def test_create_with_duplicate_barcode_is_rejected(self) -> None:
        self.make_product(name="Arroz", barcode="7751234567890")
        with self.assertRaises(ConflictError):
            self.make_product(name="Otro arroz", barcode="7751234567890")

    def test_update_does_not_change_stock(self) -> None:
        product_id = self.make_product(stock=8)
        self.ctx.products.update(
            product_id,
            {
                "name": "Arroz extra 1 kg",
                "sku": self.ctx.products.get(product_id)["sku"],
                "barcode": "7759999999999",
                "category_id": self.category_id,
                "unit": "pieza",
                "cost_cents": 350,
                "price_cents": 550,
                "stock": 999,
                "min_stock": 3,
                "active": True,
            },
        )
        product = self.ctx.products.get(product_id)
        self.assertEqual(product["name"], "Arroz extra 1 kg")
        self.assertEqual(product["price_cents"], 550)
        self.assertEqual(product["stock"], 8)
        self.assertEqual(self.ctx.inventory.list_movements(product_id=product_id)[0]["kind"], "inicial")

    def test_deactivate_and_activate_product(self) -> None:
        product_id = self.make_product()
        self.ctx.products.set_active(product_id, False)
        self.assertFalse(bool(self.ctx.products.get(product_id)["active"]))
        self.assertEqual(self.ctx.products.list(active=True), [])
        self.ctx.products.set_active(product_id, True)
        self.assertTrue(bool(self.ctx.products.get(product_id)["active"]))

    def test_rejects_invalid_price_and_name(self) -> None:
        with self.assertRaises(ValidationError):
            self.ctx.products.create(
                {
                    "name": "Producto",
                    "category_id": self.category_id,
                    "price_cents": 0,
                    "stock": 1,
                }
            )
        with self.assertRaises(ValidationError):
            self.ctx.products.create(
                {
                    "name": "X",
                    "category_id": self.category_id,
                    "price_cents": 100,
                }
            )

    def test_category_is_unique_case_insensitive(self) -> None:
        self.ctx.products.create_category("Conservas")
        with self.assertRaises(ConflictError):
            self.ctx.products.create_category("conservas")

    def test_find_by_sku_and_barcode(self) -> None:
        product_id = self.make_product(name="Leche", barcode="7751111111111")
        product = self.ctx.products.get(product_id)
        self.assertEqual(self.ctx.products.find_by_code("7751111111111")["id"], product_id)
        self.assertEqual(self.ctx.products.find_by_code(product["sku"].lower())["id"], product_id)
        self.assertIsNone(self.ctx.products.find_by_code("no-existe"))

    def test_low_stock_filter(self) -> None:
        self.make_product(name="Bajo", stock=1, min_stock=2)
        self.make_product(name="Normal", stock=10, min_stock=2)
        low = self.ctx.products.low_stock()
        self.assertEqual([product["name"] for product in low], ["Bajo"])


if __name__ == "__main__":
    unittest.main()
