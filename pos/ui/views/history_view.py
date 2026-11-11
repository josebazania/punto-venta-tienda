from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import (
    Card,
    DataTable,
    PageHeader,
    button,
    confirm,
    label,
    show_error,
    show_info,
    table_item,
)
from pos.ui.dialogs.sale_detail_dialog import SaleDetailDialog
from pos.ui.theme import DANGER, MUTED, SUCCESS, TEXT


class HistoryView(QWidget):
    data_changed = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.sales: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = PageHeader(
            "Historial de ventas",
            "Consulta comprobantes, revisa detalles y anula ventas cuando sea necesario.",
        )
        self.detail_button = button("Ver detalle")
        self.detail_button.clicked.connect(self._view_detail)
        self.pdf_button = button("Generar PDF")
        self.pdf_button.clicked.connect(self._generate_pdf)
        self.cancel_button = button("Anular venta", "Danger")
        self.cancel_button.clicked.connect(self._cancel_sale)
        header.add_action(self.pdf_button)
        header.add_action(self.detail_button)
        header.add_action(self.cancel_button)
        root.addWidget(header)

        card = Card("Ventas registradas")
        quick_filters = QHBoxLayout()
        quick_filters.setSpacing(8)
        quick_filters.addWidget(label("Periodo:", "Muted"))
        for title, period in (("Hoy", "hoy"), ("Ayer", "ayer"),
                              ("Esta semana", "semana"), ("Este mes", "mes")):
            quick_button = button(title)
            quick_button.clicked.connect(lambda checked=False, value=period: self._select_period(value))
            quick_filters.addWidget(quick_button)
        quick_filters.addStretch(1)
        card.body().addLayout(quick_filters)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(label("Desde", "Muted"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setDate(QDate.currentDate().addDays(-30))
        self.from_date.setMaximumDate(QDate.currentDate())
        filters.addWidget(self.from_date)
        filters.addWidget(label("Hasta", "Muted"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setMaximumDate(QDate.currentDate())
        filters.addWidget(self.to_date)
        self.status_combo = QComboBox()
        self.status_combo.addItem("Todas", None)
        self.status_combo.addItem("Completadas", config.SALE_COMPLETED)
        self.status_combo.addItem("Anuladas", config.SALE_CANCELLED)
        filters.addWidget(self.status_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Folio o producto…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self.refresh)
        filters.addWidget(self.search_edit, 1)
        apply_button = button("Filtrar", "Primary")
        apply_button.clicked.connect(self.refresh)
        filters.addWidget(apply_button)
        card.body().addLayout(filters)

        summary_row = QHBoxLayout()
        self.feedback_label = label("", "Hint")
        self.feedback_label.setVisible(False)
        summary_row.addWidget(self.feedback_label)
        summary_row.addStretch(1)
        self.summary_label = label("", "Muted")
        summary_row.addWidget(self.summary_label)
        card.body().addLayout(summary_row)

        self.table = DataTable()
        self.table.configure(
            ("Folio", "Fecha", "Artículos", "Pago", "Total", "Estado"),
            (155, 140, 90, 110, 110, 0),
        )
        self.table.cellDoubleClicked.connect(lambda *_: self._view_detail())
        self.table.itemSelectionChanged.connect(self._update_actions)
        card.body().addWidget(self.table, 1)
        root.addWidget(card, 1)
        self._update_actions()

    def _select_period(self, period: str) -> None:
        today = QDate.currentDate()
        self.from_date.setMaximumDate(today)
        self.to_date.setMaximumDate(today)
        if period == "hoy":
            start = end = today
        elif period == "ayer":
            start = end = today.addDays(-1)
        elif period == "semana":
            start, end = today.addDays(1 - today.dayOfWeek()), today
        elif period == "mes":
            start, end = QDate(today.year(), today.month(), 1), today
        else:
            return
        self.from_date.setDate(start)
        self.to_date.setDate(end)
        self.refresh()

    def refresh(self) -> None:
        date_from = self.from_date.date().toString(Qt.ISODate)
        date_to = self.to_date.date().toString(Qt.ISODate)
        if date_from > date_to:
            self._feedback("La fecha inicial no puede ser posterior a la final.", error=True)
            return
        try:
            self.sales = self.ctx.sales.list(
                date_from=date_from,
                date_to=date_to,
                status=self.status_combo.currentData(),
                search=self.search_edit.text(),
                limit=600,
            )
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self.table.clear_rows()
        completed_total = 0
        for sale in self.sales:
            if sale["status"] == config.SALE_COMPLETED:
                completed_total += int(sale["total_cents"])
            row = self.table.rowCount()
            self.table.insertRow(row)
            cancelled = sale["status"] == config.SALE_CANCELLED
            self.table.setItem(
                row,
                0,
                table_item(
                    sale["folio"],
                    data=int(sale["id"]),
                    bold=True,
                    color=MUTED if cancelled else None,
                ),
            )
            self.table.setItem(
                row, 1, table_item(config.format_datetime(sale["created_at"]))
            )
            self.table.setItem(
                row,
                2,
                table_item(
                    config.quantity(sale["item_units"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.table.setItem(
                row,
                3,
                table_item(config.PAYMENT_LABELS.get(sale["payment_method"], "—")),
            )
            self.table.setItem(
                row,
                4,
                table_item(
                    config.money(sale["total_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=MUTED if cancelled else TEXT,
                    bold=True,
                ),
            )
            self.table.setItem(
                row,
                5,
                table_item(
                    "Anulada" if cancelled else "Completada",
                    color=DANGER if cancelled else SUCCESS,
                ),
            )
        if not self.sales:
            self.table.show_empty("No hay ventas en el periodo seleccionado.")
        self.summary_label.setText(
            f"{len(self.sales)} ventas · Completadas: {config.money(completed_total)}"
        )
        self._update_actions()

    def _selected_sale(self) -> dict | None:
        sale_id = self.table.selected_id(0)
        if sale_id is None:
            self._feedback("Selecciona una venta.", error=True)
            return None
        for sale in self.sales:
            if int(sale["id"]) == int(sale_id):
                return sale
        try:
            return self.ctx.sales.get(sale_id)
        except POSError as exc:
            show_error(self, exc)
            return None

    def _update_actions(self) -> None:
        has_selection = self.table.selected_id(0) is not None
        self.detail_button.setEnabled(has_selection)
        self.pdf_button.setEnabled(has_selection)
        self.cancel_button.setEnabled(has_selection)

    def _generate_pdf(self) -> None:
        sale = self._selected_sale()
        if sale is None:
            return
        try:
            full_sale = self.ctx.sales.get(int(sale["id"]))
            path = self.ctx.receipts.generate(
                full_sale, self.ctx.settings.get_store_info()
            )
        except Exception as exc:
            show_error(self, exc)
            return
        show_info(
            self,
            f"Boleta PDF de {full_sale['folio']} generada en:\n\n{path}",
            "PDF generado",
        )
        self._feedback(f"PDF generado: {path.name}.")

    def _view_detail(self) -> None:
        sale = self._selected_sale()
        if sale is None:
            return
        try:
            full_sale = self.ctx.sales.get(int(sale["id"]))
        except POSError as exc:
            show_error(self, exc)
            return
        SaleDetailDialog(full_sale, self.ctx, self).exec()

    def _cancel_sale(self) -> None:
        sale = self._selected_sale()
        if sale is None:
            return
        if sale["status"] == config.SALE_CANCELLED:
            self._feedback("Esta venta ya está anulada.", error=True)
            return
        reason, ok = QInputDialog.getMultiLineText(
            self,
            "Anular venta",
            f"Motivo de anulación de {sale['folio']}:",
            "",
        )
        if not ok:
            return
        if len(reason.strip()) < 3:
            self._feedback("El motivo debe tener al menos 3 caracteres.", error=True)
            return
        extra = ""
        if sale["payment_method"] == "efectivo":
            extra = (
                "\nSi la venta pertenece a una caja ya cerrada, la devolución se "
                "registrará en la caja abierta actual."
            )
        if not confirm(
            self,
            "Confirmar anulación",
            f"¿Anular la venta {sale['folio']} por {config.money(sale['total_cents'])}?"
            f"\n\nSe devolverán los productos al stock.{extra}",
        ):
            return
        try:
            cancelled = self.ctx.sales.cancel(int(sale["id"]), reason)
        except POSError as exc:
            show_error(self, exc)
            return
        try:
            self.ctx.receipts.generate(
                cancelled, self.ctx.settings.get_store_info()
            )
        except Exception:
            logging.exception(
                "No se pudo actualizar el PDF de la venta anulada %s",
                cancelled["folio"],
            )
        self.refresh()
        self._feedback(
            f"Venta {cancelled['folio']} anulada. El stock fue restaurado."
        )
        self.data_changed.emit()

    def _feedback(self, message: str, error: bool = False) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setObjectName("ErrorLabel" if error else "SuccessLabel")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.setVisible(True)
