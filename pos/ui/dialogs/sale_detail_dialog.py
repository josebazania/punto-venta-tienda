from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.receipt import build_receipt_text
from pos.ui.common import DataTable, button, divider, label, show_error, show_info, table_item
from pos.ui.dialogs.base import BaseDialog


class SaleDetailDialog(BaseDialog):
    def __init__(self, sale: dict, ctx, parent: QWidget | None = None) -> None:
        self.sale = sale
        self.ctx = ctx
        super().__init__(
            f"Venta {sale['folio']}",
            f"{config.format_datetime(sale['created_at'])} · Caja #{sale['cash_session_id']}",
            parent,
            width=720,
        )
        self._build()
        self.footer.addStretch(1)
        self.print_button = button("Imprimir comprobante")
        self.print_button.clicked.connect(self._print_receipt)
        self.footer.addWidget(self.print_button)
        self.pdf_button = button("Abrir PDF")
        self.pdf_button.clicked.connect(self._open_pdf)
        self.footer.addWidget(self.pdf_button)
        close = button("Cerrar", "Primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        self.footer.addWidget(close)

    def _open_pdf(self) -> None:
        try:
            path = self.ctx.receipts.default_path(self.sale)
            if not path.exists() or self.sale["status"] == config.SALE_CANCELLED:
                path = self.ctx.receipts.generate(self.sale, self.ctx.settings.get_store_info())
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                show_info(self, f"No se pudo abrir el visor PDF.\n\n{path}", "PDF generado")
        except Exception as exc:
            show_error(self, exc)

    def _print_receipt(self) -> None:
        try:
            text = build_receipt_text(self.sale, self.ctx.settings.get_store_info())
            if self.sale["status"] == config.SALE_CANCELLED:
                text = "*** VENTA ANULADA ***\nMotivo: " + str(self.sale.get("cancel_reason") or "Sin motivo registrado.") + "\n\n" + text
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            document = QTextDocument()
            document.setDefaultFont(QFont("Consolas", 9))
            document.setPlainText(text)
            document.print_(printer)
        except Exception as exc:
            show_error(self, exc)

    def _build(self) -> None:
        status_row = QHBoxLayout()
        completed = self.sale["status"] == config.SALE_COMPLETED
        status = label(
            "Completada" if completed else "Anulada",
            "SuccessLabel" if completed else "ErrorLabel",
        )
        status_row.addWidget(status)
        status_row.addStretch(1)
        self.body.addLayout(status_row)

        meta = QGridLayout()
        meta.setHorizontalSpacing(28)
        meta.setVerticalSpacing(4)
        items = (
            ("Método de pago", config.PAYMENT_LABELS.get(self.sale["payment_method"], "—")),
            ("Artículos", str(self.sale["item_count"])),
            ("Vendedor", "Caja principal"),
            ("Estado", "Completada" if completed else "Anulada"),
        )
        for index, (caption, value) in enumerate(items):
            column = index % 2
            row = (index // 2) * 2
            meta.addWidget(label(caption, "Tiny"), row, column)
            meta.addWidget(label(str(value), "FieldLabel"), row + 1, column)
        meta.setColumnStretch(0, 1)
        meta.setColumnStretch(1, 1)
        self.body.addLayout(meta)
        self.body.addWidget(divider())

        table = DataTable()
        table.configure(
            ("Cant.", "Producto", "P. unitario", "Importe"),
            (90, 0, 120, 120),
        )
        table.setMinimumHeight(220)
        table.setMaximumHeight(300)
        for item in self.sale["items"]:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(
                row,
                0,
                table_item(
                    f"{config.quantity(item['quantity'])} {item['unit']}",
                    align=Qt.AlignLeft | Qt.AlignVCenter,
                ),
            )
            table.setItem(row, 1, table_item(item["product_name"]))
            table.setItem(
                row,
                2,
                table_item(
                    config.money(item["unit_price_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            table.setItem(
                row,
                3,
                table_item(
                    config.money(item["line_total_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    bold=True,
                ),
            )
        if table.rowCount() == 0:
            table.show_empty("Esta venta no tiene líneas.")
        self.body.addWidget(table)

        totals = QFrame()
        totals.setObjectName("SoftPanel")
        totals_layout = QVBoxLayout(totals)
        totals_layout.setContentsMargins(16, 12, 16, 12)
        totals_layout.setSpacing(6)
        totals_layout.addLayout(
            self._total_row("Subtotal", config.money(self.sale["subtotal_cents"]))
        )
        if int(self.sale["discount_cents"]) > 0:
            totals_layout.addLayout(
                self._total_row("Descuento", f"-{config.money(self.sale['discount_cents'])}")
            )
        totals_layout.addWidget(divider())
        totals_layout.addLayout(
            self._total_row("Total", config.money(self.sale["total_cents"]), prominent=True)
        )
        if self.sale["payment_method"] == "efectivo":
            totals_layout.addLayout(
                self._total_row(
                    "Efectivo recibido", config.money(self.sale["cash_received_cents"])
                )
            )
            totals_layout.addLayout(
                self._total_row("Vuelto", config.money(self.sale["change_cents"]))
            )
        self.body.addWidget(totals)

        if self.sale["status"] == config.SALE_CANCELLED:
            reason = label(
                f"Motivo de anulación: {self.sale.get('cancel_reason') or '—'}",
                "WarningLabel",
            )
            reason.setWordWrap(True)
            self.body.addWidget(reason)

    @staticmethod
    def _total_row(caption: str, amount: str, prominent: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        left = label(caption, "FieldLabel" if prominent else "Muted")
        right = label(amount, "MoneyBig" if prominent else "FieldLabel")
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(right)
        return row
