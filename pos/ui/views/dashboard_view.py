from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.ui.common import (
    Card,
    DataTable,
    KpiCard,
    PageHeader,
    button,
    show_error,
    table_item,
)
from pos.ui.dialogs.sale_detail_dialog import SaleDetailDialog
from pos.ui.theme import DANGER, SUCCESS, WARNING


class DashboardView(QWidget):
    new_sale_requested = Signal()
    cash_requested = Signal()
    history_requested = Signal()
    inventory_requested = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        self.header = PageHeader(
            "Resumen del día",
            config.format_long_date().capitalize(),
        )
        new_sale = button("Nueva venta", "Primary")
        new_sale.clicked.connect(self.new_sale_requested.emit)
        self.header.add_action(new_sale)
        self.cash_button = button("Abrir caja")
        self.cash_button.clicked.connect(self.cash_requested.emit)
        self.header.add_action(self.cash_button)
        root.addWidget(self.header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(14)
        kpis.setVerticalSpacing(14)
        self.sales_kpi = KpiCard("Ventas de hoy", "S/ 0.00", "0 transacciones")
        self.ticket_kpi = KpiCard("Ticket promedio", "S/ 0.00", "por venta")
        self.stock_kpi = KpiCard("Stock bajo", "0", "productos por reponer")
        self.cash_kpi = KpiCard("Estado de caja", "Cerrada", "Abre la caja para vender")
        for index, widget in enumerate(
            (self.sales_kpi, self.ticket_kpi, self.stock_kpi, self.cash_kpi)
        ):
            kpis.addWidget(widget, 0, index)
            kpis.setColumnStretch(index, 1)
        root.addLayout(kpis)

        content = QHBoxLayout()
        content.setSpacing(16)

        recent = Card(
            "Últimas ventas",
            "Los movimientos más recientes del día aparecen aquí.",
        )
        history_link = button("Ver historial", "Ghost")
        history_link.clicked.connect(self.history_requested.emit)
        recent.add_header_widget(history_link)
        self.recent_table = DataTable()
        self.recent_table.configure(
            ("Folio", "Hora", "Pago", "Total", "Estado"),
            (140, 70, 105, 110, 0),
        )
        self.recent_table.setMinimumHeight(250)
        self.recent_table.cellDoubleClicked.connect(self._open_sale)
        recent.body().addWidget(self.recent_table)
        content.addWidget(recent, 3)

        low = Card("Stock bajo", "Productos en o por debajo del mínimo.")
        low_link = button("Ver inventario", "Ghost")
        low_link.clicked.connect(self.inventory_requested.emit)
        low.add_header_widget(low_link)
        self.low_table = DataTable()
        self.low_table.configure(("Producto", "Stock"), (0, 95))
        self.low_table.setMinimumHeight(250)
        self.low_table.cellDoubleClicked.connect(lambda *_: self.inventory_requested.emit())
        low.body().addWidget(self.low_table)
        content.addWidget(low, 2)

        root.addLayout(content, 1)

    def refresh(self) -> None:
        try:
            data = self.ctx.reports.dashboard()
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        today = data["today"]
        inventory = data["inventory"]
        self.sales_kpi.set_value(
            config.money(today["total_cents"]),
            f"{today['sales_count']} transacciones",
        )
        self.ticket_kpi.set_value(
            config.money(today["average_cents"]),
            "promedio por venta",
        )
        self.stock_kpi.set_value(
            str(inventory["low_stock"]),
            f"{inventory['out_of_stock']} agotados",
        )
        cash = data["cash"]
        if cash:
            self.cash_kpi.set_value(
                "Abierta",
                f"Esperado: {config.money(cash['expected_cash_cents'])}",
            )
            self.cash_kpi.value.setStyleSheet(f"color: {SUCCESS};")
            self.cash_button.setText("Ver caja")
        else:
            self.cash_kpi.set_value("Cerrada", "Abre la caja para vender")
            self.cash_kpi.value.setStyleSheet(f"color: {WARNING};")
            self.cash_button.setText("Abrir caja")

        self.recent_table.clear_rows()
        for sale in data["recent_sales"]:
            row = self.recent_table.rowCount()
            self.recent_table.insertRow(row)
            self.recent_table.setItem(
                row,
                0,
                table_item(sale["folio"], data=int(sale["id"]), bold=True),
            )
            self.recent_table.setItem(
                row,
                1,
                table_item(config.format_time(sale["created_at"])),
            )
            self.recent_table.setItem(
                row,
                2,
                table_item(config.PAYMENT_LABELS.get(sale["payment_method"], "—")),
            )
            self.recent_table.setItem(
                row,
                3,
                table_item(
                    config.money(sale["total_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    bold=True,
                ),
            )
            cancelled = sale["status"] == config.SALE_CANCELLED
            self.recent_table.setItem(
                row,
                4,
                table_item(
                    "Anulada" if cancelled else "Completada",
                    color=DANGER if cancelled else SUCCESS,
                ),
            )
            self.recent_table.setRowHeight(row, 38)
        if self.recent_table.rowCount() == 0:
            self.recent_table.show_empty("Todavía no hay ventas registradas.")

        self.low_table.clear_rows()
        for product in data["low_stock"]:
            row = self.low_table.rowCount()
            self.low_table.insertRow(row)
            stock = float(product["stock"])
            unit = product["unit"]
            self.low_table.setItem(
                row,
                0,
                table_item(
                    product["name"],
                    data=int(product["id"]),
                    tooltip=product["name"],
                ),
            )
            self.low_table.setItem(
                row,
                1,
                table_item(
                    "Agotado" if stock <= 0 else f"{config.quantity(stock)} {unit}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=DANGER if stock <= 0 else WARNING,
                    bold=True,
                ),
            )
        if self.low_table.rowCount() == 0:
            self.low_table.show_empty("Todo el stock está por encima del mínimo.")

    def _open_sale(self, row: int, column: int) -> None:
        item = self.recent_table.item(row, 0)
        if item is None:
            return
        sale_id = item.data(Qt.UserRole)
        if sale_id is None:
            return
        try:
            sale = self.ctx.sales.get(int(sale_id))
        except Exception as exc:
            show_error(self, exc)
            return
        SaleDetailDialog(sale, self.ctx, self).exec()
