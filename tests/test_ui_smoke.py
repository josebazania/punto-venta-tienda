from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from pos.context import AppContext  # noqa: E402
from pos.db.database import Database  # noqa: E402
from pos.ui.common import dialog_accepted  # noqa: E402
from pos.ui.dialogs.cash_dialogs import CloseCashDialog  # noqa: E402
from pos.ui.dialogs.inventory_dialog import InventoryDialog  # noqa: E402
from pos.ui.dialogs.payment_dialog import PaymentDialog  # noqa: E402
from pos.ui.dialogs.product_dialog import ProductDialog  # noqa: E402
from pos.ui.dialogs.receipt_dialog import ReceiptDialog
from pos.ui.dialogs.sale_detail_dialog import SaleDetailDialog  # noqa: E402
from pos.ui.main_window import MainWindow  # noqa: E402
from pos.ui.theme import apply_theme  # noqa: E402


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "ui.db", demo_data=True)
        self.pdf_dir = Path(self._tmp.name) / "boletas"
        self.ctx = AppContext(self.db, pdf_dir=self.pdf_dir)
        self.product = self.ctx.products.list(limit=1)[0]
        self.ctx.cash.open(10000)
        self.window = MainWindow(self.ctx)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self._tmp.cleanup()

    def test_all_views_load_and_sale_cart_works(self) -> None:
        self.assertEqual(self.window.stack.count(), 8)
        for index in range(8):
            self.window.navigate(index)
            self.app.processEvents()
            self.assertIsNotNone(self.window.stack.currentWidget())
        self.window.navigate(1)
        self.app.processEvents()
        self.window.sale_view._add_product(self.product)
        self.assertEqual(len(self.window.sale_view.cart), 1)
        self.assertEqual(self.window.sale_view.cart_table.rowCount(), 1)
        self.assertIn("S/", self.window.sale_view.total_label.text())
        self.window.sale_view._increment()
        self.assertEqual(
            self.window.sale_view.cart[int(self.product["id"])]["quantity"], 2
        )
        self.window.sale_view._remove_selected()
        self.assertEqual(self.window.sale_view.cart, {})

    def test_dialogs_can_be_constructed(self) -> None:
        product = self.ctx.products.get(int(self.product["id"]))
        ProductDialog(self.ctx, product, self.window)
        InventoryDialog(self.ctx, product, "entrada", self.window)
        PaymentDialog(1000, self.window)
        sale = self.ctx.sales.checkout(
            [{"product_id": int(product["id"]), "quantity": 1}],
            payment_method="efectivo",
            cash_received_cents=int(product["price_cents"]),
        )
        ReceiptDialog(sale, self.ctx.settings.get_store_info(), self.window)
        summary = self.ctx.cash.current()
        CloseCashDialog(self.ctx, summary, self.window)
        self.assertEqual(sale["status"], "completada")

    def test_sale_detail_opens_pdf_and_prints_cancelled_status(self) -> None:
        sale = self.ctx.sales.checkout(
            [{"product_id": int(self.product["id"]), "quantity": 1}],
            payment_method="tarjeta",
        )
        detail = SaleDetailDialog(sale, self.ctx, self.window)
        with patch("pos.ui.dialogs.sale_detail_dialog.QDesktopServices.openUrl", return_value=True) as opened:
            detail.pdf_button.click()
        path = self.ctx.receipts.default_path(sale)
        self.assertTrue(path.exists())
        self.assertEqual(Path(opened.call_args.args[0].toLocalFile()), path)
        cancelled = self.ctx.sales.cancel(sale["id"], "Pedido devuelto")
        detail = SaleDetailDialog(cancelled, self.ctx, self.window)
        with patch("pos.ui.dialogs.sale_detail_dialog.QPrintDialog") as dialog, \
             patch("pos.ui.dialogs.sale_detail_dialog.QTextDocument") as document:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            detail.print_button.click()
        text = document.return_value.setPlainText.call_args.args[0]
        self.assertIn("VENTA ANULADA", text)
        self.assertIn("Pedido devuelto", text)
        document.return_value.print_.assert_called_once()

    def test_sales_period_filters_use_calendar_dates(self) -> None:
        view = self.window.history_view
        today = QDate.currentDate()
        expected = {
            "hoy": (today, today),
            "ayer": (today.addDays(-1), today.addDays(-1)),
            "semana": (today.addDays(1 - today.dayOfWeek()), today),
            "mes": (QDate(today.year(), today.month(), 1), today),
        }
        for period, (start, end) in expected.items():
            with self.subTest(period=period), patch.object(view.ctx.sales, "list", return_value=[]) as sales_list:
                view._select_period(period)
                self.assertEqual(view.from_date.date(), start)
                self.assertEqual(view.to_date.date(), end)
                self.assertEqual(sales_list.call_args.kwargs["date_from"], start.toString("yyyy-MM-dd"))
                self.assertEqual(sales_list.call_args.kwargs["date_to"], end.toString("yyyy-MM-dd"))

    def test_navigation_and_data_refresh(self) -> None:
        self.window.navigate(0)
        self.assertIn("Ventas de hoy", self.window.dashboard_view.sales_kpi.caption.text())
        self.window.navigate(2)
        self.assertGreaterEqual(self.window.products_view.table.rowCount(), 20)
        self.window.navigate(3)
        self.assertGreaterEqual(self.window.inventory_view.table.rowCount(), 20)
        self.window.navigate(4)
        self.window._refresh_current()
        self.app.processEvents()

    def test_dialog_accepted_helper_uses_dialog_code_enum(self) -> None:
        class AcceptedDialog:
            def exec(self):
                return QDialog.DialogCode.Accepted

        class RejectedDialog:
            def exec(self):
                return QDialog.DialogCode.Rejected

        self.assertTrue(dialog_accepted(AcceptedDialog()))  # type: ignore[arg-type]
        self.assertFalse(dialog_accepted(RejectedDialog()))  # type: ignore[arg-type]

    def test_accepted_dialog_flows(self) -> None:
        class FakeOpenCashDialog:
            result_data = {"id": 1}

            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self):
                return QDialog.DialogCode.Accepted

        class FakeProductDialog:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self):
                return QDialog.DialogCode.Accepted

        class FakeInventoryDialog:
            result_data = {"product_name": "Prueba", "stock": 2}

            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self):
                return QDialog.DialogCode.Accepted

        class FakePaymentDialog:
            def __init__(self, subtotal_cents: int, parent=None) -> None:
                self.result_data = {
                    "discount_cents": 0,
                    "payment_method": "efectivo",
                    "cash_received_cents": subtotal_cents,
                }

            def exec(self):
                return QDialog.DialogCode.Accepted

        class FakeReceiptDialog:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self):
                return QDialog.DialogCode.Accepted

        # Abrir caja desde la vista.
        with patch("pos.ui.views.cash_view.OpenCashDialog", FakeOpenCashDialog):
            self.window.cash_view.open_cash()

        # Editar un producto desde la tabla.
        self.window.navigate(2)
        self.window.products_view.table.selectRow(0)
        with patch("pos.ui.views.products_view.ProductDialog", FakeProductDialog):
            self.window.products_view._edit_selected()

        # Registrar una entrada de inventario.
        self.window.navigate(3)
        self.window.inventory_view.table.selectRow(0)
        with patch("pos.ui.views.inventory_view.InventoryDialog", FakeInventoryDialog):
            self.window.inventory_view._open_dialog("entrada")

        # Cobrar una venta completa y cerrar el comprobante.
        self.window.navigate(1)
        self.window.sale_view._add_product(self.product)
        with (
            patch("pos.ui.views.sale_view.PaymentDialog", FakePaymentDialog),
            patch("pos.ui.views.sale_view.ReceiptDialog", FakeReceiptDialog),
        ):
            self.window.sale_view.checkout()
        self.assertEqual(self.window.sale_view.cart, {})
        self.assertEqual(len(self.ctx.sales.list()), 1)
        self.assertEqual(self.ctx.sales.list()[0]["status"], "completada")
        generated = list(self.pdf_dir.rglob("*.pdf"))
        self.assertEqual(len(generated), 1)
        self.assertTrue(generated[0].read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()

