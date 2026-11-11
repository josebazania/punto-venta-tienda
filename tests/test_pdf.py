from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtPdf import QPdfDocument  # noqa: E402

from pos.context import AppContext  # noqa: E402
from pos.db.database import Database  # noqa: E402
from pos.services.pdf import build_sale_pdf_html  # noqa: E402


class PdfReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.pdf_dir = Path(self._tmp.name) / "boletas"
        self.db = Database(Path(self._tmp.name) / "pdf.db", demo_data=True)
        self.ctx = AppContext(self.db, pdf_dir=self.pdf_dir)
        self.ctx.cash.open(10000)
        products = self.ctx.products.list(limit=2)
        self.sale = self.ctx.sales.checkout(
            [
                {"product_id": products[0]["id"], "quantity": 2},
                {"product_id": products[1]["id"], "quantity": 1},
            ],
            discount_cents=100,
            payment_method="efectivo",
            cash_received_cents=5000,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pdf_is_generated_in_year_and_month_folder(self) -> None:
        path = self.ctx.receipts.generate(
            self.sale, self.ctx.settings.get_store_info()
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 5_000)
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", data)
        self.assertEqual(path.parent.parent.parent, self.pdf_dir.resolve())
        self.assertEqual(path.name, f"{self.sale['folio']}.pdf")

    def test_pdf_uses_80mm_paper_and_one_page(self) -> None:
        path = self.ctx.receipts.generate(self.sale, self.ctx.settings.get_store_info())
        pdf = QPdfDocument()
        self.assertEqual(pdf.load(str(path)), QPdfDocument.Error.None_)
        self.assertEqual(pdf.pageCount(), 1)
        self.assertAlmostEqual(pdf.pagePointSize(0).width(), 80 * 72 / 25.4, delta=1)
        pdf.close()

    def test_pdf_can_be_generated_in_a_custom_destination(self) -> None:
        destination = Path(self._tmp.name) / "para-enviar" / "boleta.pdf"
        path = self.ctx.receipts.generate(
            self.sale,
            self.ctx.settings.get_store_info(),
            destination,
        )
        self.assertEqual(path, destination.resolve())
        self.assertTrue(path.exists())
        self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_html_escapes_store_and_product_values(self) -> None:
        sale = dict(self.sale)
        sale["items"] = [dict(item) for item in self.sale["items"]]
        sale["items"][0]["product_name"] = "<b>Producto & peligro</b>"
        store = {
            "business_name": "Tienda <script>",
            "ruc": "123",
            "address": "Calle <principal>",
            "phone": "999",
            "receipt_footer": "Gracias & vuelva",
        }
        html = build_sale_pdf_html(sale, store)
        self.assertIn("Tienda &lt;script&gt;", html)
        self.assertIn("&lt;b&gt;Producto &amp; peligro&lt;/b&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("Gracias &amp; vuelva", html)

    def test_cancelled_sale_pdf_shows_status_and_reason(self) -> None:
        cancelled = self.ctx.sales.cancel(
            self.sale["id"], "Cliente devolvió <producto>"
        )
        html = build_sale_pdf_html(
            cancelled, self.ctx.settings.get_store_info()
        )
        self.assertIn("ANULADA", html)
        self.assertIn("Cliente devolvió &lt;producto&gt;", html)


if __name__ == "__main__":
    unittest.main()
