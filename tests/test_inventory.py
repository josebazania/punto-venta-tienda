from __future__ import annotations

import unittest

from pos.services.errors import ValidationError
from tests.base import ServiceTestCase


class InventoryServiceTests(ServiceTestCase):
    def test_entry_increases_stock_and_logs_movement(self) -> None:
        product_id = self.make_product(stock=10)
        result = self.ctx.inventory.adjust(
            product_id,
            mode="entrada",
            quantity=5,
            note="Compra a proveedor",
            reference="F-001",
        )
        self.assertEqual(result["previous_stock"], 10)
        self.assertEqual(result["stock"], 15)
        product = self.ctx.products.get(product_id)
        self.assertEqual(product["stock"], 15)
        movement = self.ctx.inventory.list_movements(product_id=product_id)[0]
        self.assertEqual(movement["kind"], "entrada")
        self.assertEqual(movement["quantity_delta"], 5)
        self.assertEqual(movement["stock_after"], 15)

    def test_waste_decreases_stock(self) -> None:
        product_id = self.make_product(stock=10)
        result = self.ctx.inventory.adjust(
            product_id,
            mode="merma",
            quantity=2.5,
            note="Producto vencido",
        )
        self.assertEqual(result["stock"], 7.5)

    def test_adjust_sets_exact_stock(self) -> None:
        product_id = self.make_product(stock=10)
        result = self.ctx.inventory.adjust(
            product_id,
            mode="ajuste",
            quantity=7.25,
            note="Conteo físico",
        )
        self.assertEqual(result["delta"], -2.75)
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 7.25)

    def test_waste_cannot_leave_negative_stock(self) -> None:
        product_id = self.make_product(stock=3)
        with self.assertRaises(ValidationError):
            self.ctx.inventory.adjust(
                product_id,
                mode="merma",
                quantity=4,
                note="Merma",
            )
        self.assertEqual(self.ctx.products.get(product_id)["stock"], 3)

    def test_adjustment_without_change_is_rejected(self) -> None:
        product_id = self.make_product(stock=3)
        with self.assertRaises(ValidationError):
            self.ctx.inventory.adjust(
                product_id,
                mode="ajuste",
                quantity=3,
                note="Conteo",
            )

    def test_reason_required_for_waste_and_adjustment(self) -> None:
        product_id = self.make_product(stock=3)
        for mode in ("merma", "ajuste"):
            with self.assertRaises(ValidationError):
                self.ctx.inventory.adjust(
                    product_id,
                    mode=mode,
                    quantity=1,
                    note="",
                )

    def test_quantity_precision_is_limited_to_three_decimals(self) -> None:
        product_id = self.make_product(stock=3)
        with self.assertRaises(ValidationError):
            self.ctx.inventory.adjust(
                product_id,
                mode="entrada",
                quantity=1.2345,
                note="Entrada",
            )


if __name__ == "__main__":
    unittest.main()
