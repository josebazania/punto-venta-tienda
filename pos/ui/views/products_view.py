from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.services.product_import import export_products, import_products, save_template
from pos.ui.common import (
    Card,
    DataTable,
    PageHeader,
    button,
    confirm,
    dialog_accepted,
    label,
    show_error,
    table_item,
)
from pos.ui.dialogs.product_dialog import ProductDialog
from pos.ui.theme import DANGER, MUTED, SUCCESS, WARNING


class ProductsView(QWidget):
    data_changed = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.products: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = PageHeader(
            "Productos",
            "Administra el catálogo, los precios y la disponibilidad.",
        )
        self.edit_button = button("Editar")
        self.edit_button.clicked.connect(self._edit_selected)
        self.toggle_button = button("Desactivar")
        self.toggle_button.clicked.connect(self._toggle_selected)
        template_button = button("Plantilla Excel")
        template_button.clicked.connect(self._save_import_template)
        import_button = button("Importar Excel")
        import_button.clicked.connect(self._import_excel)
        export_button = button("Exportar Excel")
        export_button.clicked.connect(self._export_excel)
        header.add_action(export_button)
        header.add_action(template_button)
        header.add_action(import_button)
        new_button = button("Nuevo producto", "Primary")
        new_button.clicked.connect(self._new_product)
        header.add_action(self.edit_button)
        header.add_action(self.toggle_button)
        header.add_action(new_button)
        root.addWidget(header)

        card = Card("Catálogo de productos", "Doble clic en una fila para editarla.")
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por nombre, código o barras…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(360)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._load)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        filters.addWidget(self.search_edit, 1)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(160)
        self.category_combo.currentIndexChanged.connect(self._load)
        filters.addWidget(self.category_combo)
        self.status_combo = QComboBox()
        self.status_combo.addItem("Activos", True)
        self.status_combo.addItem("Inactivos", False)
        self.status_combo.addItem("Todos", None)
        self.status_combo.currentIndexChanged.connect(self._load)
        filters.addWidget(self.status_combo)
        filters.addStretch(1)
        self.count_label = label("", "Muted")
        filters.addWidget(self.count_label)
        card.body().addLayout(filters)

        self.feedback_label = label("", "Hint")
        self.feedback_label.setVisible(False)
        card.body().addWidget(self.feedback_label)

        self.table = DataTable()
        self.table.configure(
            (
                "Código",
                "Producto",
                "Categoría",
                "Unidad",
                "Precio",
                "Costo",
                "Stock",
                "Mín.",
                "Estado",
            ),
            (92, 0, 130, 80, 95, 95, 88, 65, 90),
        )
        self.table.cellDoubleClicked.connect(lambda *_: self._edit_selected())
        self.table.itemSelectionChanged.connect(self._update_actions)
        card.body().addWidget(self.table, 1)
        root.addWidget(card, 1)

        self._update_actions()

    def refresh(self) -> None:
        selected_category = self.category_combo.currentData()
        try:
            categories = self.ctx.products.categories()
            self.category_combo.blockSignals(True)
            self.category_combo.clear()
            self.category_combo.addItem("Todas las categorías", None)
            for category in categories:
                self.category_combo.addItem(
                    f"{category['name']} ({category['product_count']})",
                    int(category["id"]),
                )
            if selected_category is not None:
                index = self.category_combo.findData(int(selected_category))
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
            self.category_combo.blockSignals(False)
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self._load()

    def _load(self) -> None:
        try:
            self.products = self.ctx.products.list(
                search=self.search_edit.text(),
                category_id=self.category_combo.currentData(),
                active=self.status_combo.currentData(),
                limit=800,
            )
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self.table.clear_rows()
        for product in self.products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(
                row,
                0,
                table_item(
                    product["sku"],
                    data=int(product["id"]),
                    tooltip=product.get("barcode") or "Sin código de barras",
                ),
            )
            self.table.setItem(row, 1, table_item(product["name"], tooltip=product["name"]))
            self.table.setItem(row, 2, table_item(product.get("category_name") or "—"))
            self.table.setItem(row, 3, table_item(product["unit"]))
            self.table.setItem(
                row,
                4,
                table_item(
                    config.money(product["price_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    bold=True,
                ),
            )
            self.table.setItem(
                row,
                5,
                table_item(
                    config.money(product["cost_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            stock = float(product["stock"])
            minimum = float(product["min_stock"])
            stock_color = (
                DANGER
                if stock <= 0
                else WARNING
                if stock <= minimum
                else None
            )
            self.table.setItem(
                row,
                6,
                table_item(
                    f"{config.quantity(stock)}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=stock_color,
                    bold=stock_color is not None,
                ),
            )
            self.table.setItem(
                row,
                7,
                table_item(
                    f"{config.quantity(minimum)}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.table.setItem(
                row,
                8,
                table_item(
                    "Activo" if product["active"] else "Inactivo",
                    color=SUCCESS if product["active"] else MUTED,
                ),
            )
        if not self.products:
            self.table.show_empty("No hay productos con esos filtros.")
        self.count_label.setText(f"{len(self.products)} productos")
        self._update_actions()

    def _selected_product(self) -> dict | None:
        product_id = self.table.selected_id(0)
        if product_id is None:
            return None
        try:
            return self.ctx.products.get(product_id)
        except Exception as exc:
            show_error(self, exc)
            return None

    def _update_actions(self) -> None:
        has_selection = self.table.selected_id(0) is not None
        self.edit_button.setEnabled(has_selection)
        self.toggle_button.setEnabled(has_selection)
        product = self._peek_selected()
        self.toggle_button.setText(
            "Desactivar" if product is None or product["active"] else "Activar"
        )

    def _peek_selected(self) -> dict | None:
        product_id = self.table.selected_id(0)
        if product_id is None:
            return None
        for product in self.products:
            if int(product["id"]) == int(product_id):
                return product
        return None

    def _export_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar catálogo", "productos.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            count = export_products(path, self.ctx.products)
        except Exception as exc:
            show_error(self, exc)
            return
        QMessageBox.information(self, "Exportación completa", f"Se exportaron {count} productos a:\n{path}")

    def _save_import_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar plantilla", "plantilla_productos.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            save_template(path)
        except Exception as exc:
            show_error(self, exc)
            return
        QMessageBox.information(self, "Plantilla guardada", "Completa nombre y precio en soles. Las demás columnas son opcionales. Las categorías deben existir previamente; escribe los códigos de barras como texto.")

    def _import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar productos", "", "Excel (*.xlsx)")
        if not path:
            return
        if not confirm(self, "Importar productos", "Se crearán los productos válidos; las filas con errores se omitirán. Los productos existentes no se modificarán. ¿Continuar?"):
            return
        try:
            count, errors = import_products(path, self.ctx.products)
        except Exception as exc:
            show_error(self, exc)
            return
        if count:
            self.refresh()
            self.data_changed.emit()
        message = f"Productos importados: {count}.\nFilas con errores: {len(errors)}."
        result = QMessageBox(self)
        result.setWindowTitle("Resultado de importación")
        result.setText(message)
        if errors:
            result.setInformativeText("Consulta los detalles para corregir las filas que no se importaron.")
            result.setDetailedText("\n".join(errors))
        result.exec()

    def _new_product(self) -> None:
        dialog = ProductDialog(self.ctx, parent=self)
        if dialog_accepted(dialog):
            self.refresh()
            self._feedback("Producto creado correctamente.")
            self.data_changed.emit()

    def _edit_selected(self) -> None:
        product = self._selected_product()
        if product is None:
            self._feedback("Selecciona un producto para editarlo.", error=True)
            return
        dialog = ProductDialog(self.ctx, product, self)
        if dialog_accepted(dialog):
            self.refresh()
            self._feedback("Cambios guardados.")
            self.data_changed.emit()

    def _toggle_selected(self) -> None:
        product = self._selected_product()
        if product is None:
            self._feedback("Selecciona un producto.", error=True)
            return
        new_state = not bool(product["active"])
        action = "activar" if new_state else "desactivar"
        if not confirm(
            self,
            f"{action.capitalize()} producto",
            f"¿Deseas {action} «{product['name']}»?"
            + ("" if new_state else "\n\nDejará de aparecer en el punto de venta."),
        ):
            return
        try:
            self.ctx.products.set_active(int(product["id"]), new_state)
        except POSError as exc:
            show_error(self, exc)
            return
        self.refresh()
        self._feedback(
            f"Producto {'activado' if new_state else 'desactivado'} correctamente."
        )
        self.data_changed.emit()

    def _feedback(self, message: str, error: bool = False) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setObjectName("ErrorLabel" if error else "SuccessLabel")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.setVisible(True)
        QTimer.singleShot(4500, lambda: self.feedback_label.setVisible(False))
