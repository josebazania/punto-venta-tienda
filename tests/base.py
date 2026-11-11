from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pos.context import AppContext
from pos.db.database import Database


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "test.db", demo_data=False)
        self.ctx = AppContext(self.db)
        categories = self.ctx.products.categories()
        self.category_id = int(categories[0]["id"])
        self._barcode_counter = 0

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_product(
        self,
        *,
        name: str = "Arroz 1 kg",
        price_cents: int = 500,
        cost_cents: int = 300,
        stock: float = 10.0,
        min_stock: float = 2.0,
        barcode: str | None = None,
        unit: str = "pieza",
        active: bool = True,
    ) -> int:
        self._barcode_counter += 1
        if barcode is None:
            barcode = f"775{self._barcode_counter:010d}"
        return self.ctx.products.create(
            {
                "name": name,
                "barcode": barcode,
                "category_id": self.category_id,
                "unit": unit,
                "cost_cents": cost_cents,
                "price_cents": price_cents,
                "stock": stock,
                "min_stock": min_stock,
                "active": active,
            }
        )

    def open_cash(self, opening_cents: int = 10000) -> dict:
        return self.ctx.cash.open(opening_cents)
