from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import (
    button,
    label,
    money_spinbox,
    quantity_spinbox,
)
from pos.ui.dialogs.base import BaseDialog


class ProductDialog(BaseDialog):
    def __init__(
        self,
        ctx: AppContext,
        product: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.ctx = ctx
        self.product = product
        editing = product is not None
        super().__init__(
            "Editar producto" if editing else "Nuevo producto",
            "Actualiza la información del catálogo."
            if editing
            else "Registra un producto para venderlo y controlar su stock.",
            parent,
            width=580,
        )
        self.saved_id: int | None = int(product["id"]) if product else None
        self._build(editing)
        self.add_cancel()
        primary = self.add_primary("Guardar cambios" if editing else "Crear producto")
        primary.clicked.connect(self._save)

    def _build(self, editing: bool) -> None:
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ej. Arroz Costeño 1 kg")
        self.name_edit.setMaxLength(120)
        form.addWidget(label("Nombre del producto", "FieldLabel"), 0, 0)
        form.addWidget(label("Código interno", "FieldLabel"), 0, 1)
        form.addWidget(self.name_edit, 1, 0)
        self.sku_edit = QLineEdit()
        self.sku_edit.setReadOnly(True)
        self.sku_edit.setPlaceholderText("Automático")
        form.addWidget(self.sku_edit, 1, 1)

        self.barcode_edit = QLineEdit()
        self.barcode_edit.setPlaceholderText("Opcional, escanéalo aquí")
        self.barcode_edit.setMaxLength(64)
        form.addWidget(label("Código de barras", "FieldLabel"), 2, 0)
        form.addWidget(label("Unidad de venta", "FieldLabel"), 2, 1)
        form.addWidget(self.barcode_edit, 3, 0)
        self.unit_combo = QComboBox()
        for unit in config.UNITS:
            self.unit_combo.addItem(unit.capitalize(), unit)
        form.addWidget(self.unit_combo, 3, 1)

        form.addWidget(label("Categoría", "FieldLabel"), 4, 0)
        category_row = QHBoxLayout()
        category_row.setSpacing(6)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(180)
        add_category = button("+ Nueva", "Small")
        add_category.clicked.connect(self._new_category)
        category_row.addWidget(self.category_combo, 1)
        category_row.addWidget(add_category, 0)
        form.addLayout(category_row, 5, 0)
        form.addWidget(label("Estado", "FieldLabel"), 4, 1)
        self.active_check = QCheckBox("Producto activo para la venta")
        form.addWidget(self.active_check, 5, 1)

        self.cost_spin = money_spinbox()
        self.price_spin = money_spinbox()
        form.addWidget(label("Costo de compra", "FieldLabel"), 6, 0)
        form.addWidget(label("Precio de venta", "FieldLabel"), 6, 1)
        form.addWidget(self.cost_spin, 7, 0)
        form.addWidget(self.price_spin, 7, 1)

        self.min_spin = quantity_spinbox()
        form.addWidget(label("Stock mínimo (alerta)", "FieldLabel"), 8, 0)
        self.stock_spin = quantity_spinbox()
        self.stock_label = label("Stock inicial", "FieldLabel")
        form.addWidget(self.stock_label, 8, 1)
        form.addWidget(self.min_spin, 9, 0)
        form.addWidget(self.stock_spin, 9, 1)

        self.body.addLayout(form)
        self.stock_note = label(
            "El stock se modifica desde Inventario para conservar el historial.",
            "Hint",
        )
        self.stock_note.setWordWrap(True)
        self.body.addWidget(self.stock_note)

        self._load_categories()
        if self.product:
            self._fill(self.product)

    def _load_categories(self, selected_id: int | None = None) -> None:
        current = self.product["category_id"] if self.product else None
        selected = selected_id if selected_id is not None else current
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("Sin categoría", None)
        categories = self.ctx.products.categories()
        for category in categories:
            self.category_combo.addItem(category["name"], int(category["id"]))
        if selected is not None:
            index = self.category_combo.findData(int(selected))
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        self.category_combo.blockSignals(False)

    def _fill(self, product: dict) -> None:
        self.name_edit.setText(product["name"])
        self.sku_edit.setText(product["sku"])
        self.barcode_edit.setText(product.get("barcode") or "")
        index = self.unit_combo.findData(product["unit"])
        self.unit_combo.setCurrentIndex(max(index, 0))
        self.active_check.setChecked(bool(product["active"]))
        self.cost_spin.setValue(int(product["cost_cents"]) / 100)
        self.price_spin.setValue(int(product["price_cents"]) / 100)
        self.min_spin.setValue(float(product["min_stock"]))
        self.stock_spin.setValue(float(product["stock"]))
        self.stock_spin.setEnabled(False)
        self.stock_spin.setToolTip("Usa Inventario para modificar las existencias.")
        self.stock_label.setText("Stock actual")
        self.stock_note.setText(
            "Para cambiar el stock usa los movimientos de Inventario. "
            "Así queda registrado quién, cuándo y por qué."
        )

    def _new_category(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Nueva categoría", "Nombre de la categoría:"
        )
        if not ok:
            return
        try:
            category_id = self.ctx.products.create_category(name)
        except POSError as exc:
            self.show_error(exc.message)
            return
        self.clear_error()
        self._load_categories(selected_id=category_id)

    def _save(self) -> None:
        self.clear_error()
        data = {
            "name": self.name_edit.text(),
            "sku": self.product["sku"] if self.product else "",
            "barcode": self.barcode_edit.text(),
            "category_id": self.category_combo.currentData(),
            "unit": self.unit_combo.currentData(),
            "cost_cents": int(round(self.cost_spin.value() * 100)),
            "price_cents": int(round(self.price_spin.value() * 100)),
            "stock": round(self.stock_spin.value(), 3),
            "min_stock": round(self.min_spin.value(), 3),
            "active": self.active_check.isChecked(),
        }
        try:
            if self.product:
                self.ctx.products.update(int(self.product["id"]), data)
                self.saved_id = int(self.product["id"])
            else:
                self.saved_id = self.ctx.products.create(data)
        except POSError as exc:
            self.show_error(exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensivo
            self.show_error(f"No se pudo guardar el producto: {exc}")
            return
        self.accept()
