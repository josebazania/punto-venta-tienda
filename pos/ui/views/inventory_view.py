from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
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
    KpiCard,
    PageHeader,
    button,
    dialog_accepted,
    label,
    show_error,
    table_item,
)
from pos.ui.dialogs.inventory_dialog import InventoryDialog
from pos.ui.theme import DANGER, MUTED, SUCCESS, WARNING

_KIND_LABELS = {
    "inicial": "Inicial",
    "venta": "Venta",
    "cancelacion": "Anulación",
    "entrada": "Entrada",
    "merma": "Merma",
    "ajuste": "Ajuste",
}


class InventoryView(QWidget):
    data_changed = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.products: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(12)

        header = PageHeader(
            "Inventario",
            "Existencias, valorización y movimientos auditables del almacén.",
        )
        entry = button("Entrada de mercancía", "Primary")
        entry.clicked.connect(lambda: self._open_dialog("entrada"))
        waste = button("Registrar merma")
        waste.clicked.connect(lambda: self._open_dialog("merma"))
        adjust = button("Ajustar stock")
        adjust.clicked.connect(lambda: self._open_dialog("ajuste"))
        header.add_action(waste)
        header.add_action(adjust)
        header.add_action(entry)
        root.addWidget(header)

        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.active_kpi = KpiCard("Productos activos", "0")
        self.value_kpi = KpiCard("Valor del inventario", "S/ 0.00", "al costo")
        self.low_kpi = KpiCard("Stock bajo", "0", "por reponer")
        self.out_kpi = KpiCard("Agotados", "0", "sin existencias")
        for widget in (self.active_kpi, self.value_kpi, self.low_kpi, self.out_kpi):
            widget.setFixedHeight(98)
            kpis.addWidget(widget, 1)
        root.addLayout(kpis)

        stock_card = Card("Existencias", "Selecciona un producto para registrar un movimiento.")
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar producto por nombre o código…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(340)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._load)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        filters.addWidget(self.search_edit, 1)
        self.low_check = QCheckBox("Solo stock bajo")
        self.low_check.stateChanged.connect(self._load)
        filters.addWidget(self.low_check)
        filters.addStretch(1)
        self.count_label = label("", "Muted")
        filters.addWidget(self.count_label)
        stock_card.body().addLayout(filters)

        self.feedback_label = label("", "Hint")
        self.feedback_label.setVisible(False)
        stock_card.body().addWidget(self.feedback_label)

        self.table = DataTable()
        self.table.configure(
            ("Producto", "Código", "Categoría", "Stock", "Mínimo", "Estado", "Valor al costo"),
            (0, 90, 135, 95, 80, 105, 120),
        )
        self.table.setMinimumHeight(190)
        stock_card.body().addWidget(self.table, 1)
        root.addWidget(stock_card, 3)

        movements_card = Card("Últimos movimientos", "Historial de entradas, ventas y ajustes.")
        self.movements_table = DataTable()
        self.movements_table.configure(
            ("Fecha", "Producto", "Tipo", "Cambio", "Stock final", "Nota"),
            (132, 0, 95, 85, 95, 180),
        )
        self.movements_table.setMinimumHeight(115)
        movements_card.body().addWidget(self.movements_table)
        root.addWidget(movements_card, 2)

    def refresh(self) -> None:
        try:
            overview = self.ctx.reports.inventory_overview()
            self.products = self.ctx.products.list(
                search=self.search_edit.text(),
                active=None,
                low_stock_only=self.low_check.isChecked(),
                limit=800,
            )
            movements = self.ctx.inventory.list_movements(limit=25)
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        stats = overview["stats"]
        self.active_kpi.set_value(str(stats["active_products"]))
        self.value_kpi.set_value(config.money(stats["stock_value_cents"]))
        self.low_kpi.set_value(str(stats["low_stock"]))
        self.out_kpi.set_value(str(stats["out_of_stock"]))
        self._fill_products()
        self._fill_movements(movements)

    def _load(self) -> None:
        try:
            self.products = self.ctx.products.list(
                search=self.search_edit.text(),
                active=None,
                low_stock_only=self.low_check.isChecked(),
                limit=800,
            )
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self._fill_products()

    def _fill_products(self) -> None:
        self.table.clear_rows()
        for product in self.products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            stock = float(product["stock"])
            minimum = float(product["min_stock"])
            if stock <= 0:
                status, color = "Agotado", DANGER
            elif stock <= minimum:
                status, color = "Stock bajo", WARNING
            else:
                status, color = "Disponible", SUCCESS
            self.table.setItem(
                row,
                0,
                table_item(
                    product["name"],
                    data=int(product["id"]),
                    tooltip=product["name"],
                ),
            )
            self.table.setItem(row, 1, table_item(product["sku"]))
            self.table.setItem(row, 2, table_item(product.get("category_name") or "—"))
            self.table.setItem(
                row,
                3,
                table_item(
                    f"{config.quantity(stock)} {product['unit']}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=color,
                    bold=True,
                ),
            )
            self.table.setItem(
                row,
                4,
                table_item(
                    f"{config.quantity(minimum)}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.table.setItem(row, 5, table_item(status, color=color, bold=True))
            value = config.line_total_cents(
                int(product["cost_cents"]), max(0.0, stock)
            )
            self.table.setItem(
                row,
                6,
                table_item(
                    config.money(value),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
        if not self.products:
            self.table.show_empty("No hay productos para los filtros seleccionados.")
        self.count_label.setText(f"{len(self.products)} productos")

    def _fill_movements(self, movements: list[dict]) -> None:
        self.movements_table.clear_rows()
        for movement in movements:
            row = self.movements_table.rowCount()
            self.movements_table.insertRow(row)
            self.movements_table.setItem(
                row, 0, table_item(config.format_datetime(movement["created_at"]))
            )
            self.movements_table.setItem(
                row, 1, table_item(movement["product_name"], tooltip=movement["product_name"])
            )
            kind = str(movement["kind"])
            self.movements_table.setItem(
                row,
                2,
                table_item(
                    _KIND_LABELS.get(kind, kind),
                    color=DANGER
                    if kind in {"venta", "merma"}
                    else SUCCESS
                    if kind in {"entrada", "inicial", "cancelacion"}
                    else MUTED,
                ),
            )
            delta = float(movement["quantity_delta"])
            self.movements_table.setItem(
                row,
                3,
                table_item(
                    f"{'+' if delta > 0 else ''}{config.quantity(delta)}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=SUCCESS if delta > 0 else DANGER,
                    bold=True,
                ),
            )
            self.movements_table.setItem(
                row,
                4,
                table_item(
                    config.quantity(movement["stock_after"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            note = str(movement.get("note") or movement.get("reference") or "—")
            self.movements_table.setItem(row, 5, table_item(note, tooltip=note))
        if not movements:
            self.movements_table.show_empty("Todavía no hay movimientos de inventario.")

    def _selected_product(self) -> dict | None:
        product_id = self.table.selected_id(0)
        if product_id is None:
            self._feedback("Selecciona un producto de la tabla.", error=True)
            return None
        for product in self.products:
            if int(product["id"]) == int(product_id):
                return product
        try:
            return self.ctx.products.get(product_id)
        except POSError as exc:
            show_error(self, exc)
            return None

    def _open_dialog(self, mode: str) -> None:
        product = self._selected_product()
        if product is None:
            return
        dialog = InventoryDialog(self.ctx, product, mode, self)
        if dialog_accepted(dialog) and dialog.result_data:
            result = dialog.result_data
            self.refresh()
            self._feedback(
                f"Movimiento registrado. Stock actual de «{result['product_name']}»: "
                f"{config.quantity(result['stock'])}."
            )
            self.data_changed.emit()

    def _feedback(self, message: str, error: bool = False) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setObjectName("ErrorLabel" if error else "SuccessLabel")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.setVisible(True)
        QTimer.singleShot(4500, lambda: self.feedback_label.setVisible(False))
