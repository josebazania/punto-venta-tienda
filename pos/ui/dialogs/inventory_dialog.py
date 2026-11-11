from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit, QWidget

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import label, quantity_spinbox
from pos.ui.dialogs.base import BaseDialog
from pos.ui.theme import DANGER, SUCCESS

_MODE_LABELS = {
    "entrada": "Entrada de mercancía",
    "merma": "Registrar merma",
    "ajuste": "Ajuste de inventario",
}
_MODE_HINTS = {
    "entrada": "Suma existencias al producto seleccionado.",
    "merma": "Resta existencias por producto dañado, vencido o perdido.",
    "ajuste": "Fija el stock exacto después de un conteo físico.",
}


class InventoryDialog(BaseDialog):
    def __init__(
        self,
        ctx: AppContext,
        product: dict,
        mode: str,
        parent: QWidget | None = None,
    ) -> None:
        if mode not in _MODE_LABELS:
            raise ValueError("Modo de inventario no válido")
        self.ctx = ctx
        self.product = product
        self.mode = mode
        self.result_data: dict | None = None
        super().__init__(
            _MODE_LABELS[mode],
            _MODE_HINTS[mode],
            parent,
            width=480,
        )
        self._build()
        self.add_cancel()
        primary = self.add_primary("Registrar movimiento")
        primary.clicked.connect(self._save)

    def _build(self) -> None:
        info = QFrame()
        info.setObjectName("SoftPanel")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(12, 10, 12, 10)
        text_box = QFormLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        name = label(self.product["name"], "SectionTitle")
        name.setWordWrap(True)
        text_box.addRow(name)
        self.stock_label = label(
            f"Stock actual: {config.quantity(self.product['stock'])} "
            f"{self.product['unit']}",
            "Muted",
        )
        text_box.addRow(self.stock_label)
        info_layout.addLayout(text_box)
        self.body.addWidget(info)

        form = QFormLayout()
        form.setSpacing(9)
        self.qty_spin = quantity_spinbox()
        self.qty_spin.setValue(0 if self.mode == "entrada" else float(self.product["stock"]))
        if self.mode == "merma":
            self.qty_spin.setMaximum(float(self.product["stock"]))
            self.qty_spin.setValue(0)
        form.addRow(
            "Cantidad" if self.mode != "ajuste" else "Nuevo stock exacto",
            self.qty_spin,
        )
        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText("Opcional: factura, guía, proveedor…")
        self.reference_edit.setMaxLength(80)
        form.addRow("Referencia", self.reference_edit)
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText(
            "Motivo del movimiento (obligatorio para merma y ajuste)"
        )
        self.note_edit.setFixedHeight(68)
        form.addRow("Motivo", self.note_edit)
        self.body.addLayout(form)

        self.preview = label("", "Muted")
        self.body.addWidget(self.preview)

        self.qty_spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self) -> None:
        current = float(self.product["stock"])
        value = float(self.qty_spin.value())
        if self.mode == "entrada":
            result = current + value
        elif self.mode == "merma":
            result = current - value
        else:
            result = value
        delta = result - current
        sign = "+" if delta > 0 else ""
        color = SUCCESS if result >= 0 else DANGER
        self.preview.setText(
            f"Stock resultante: {config.quantity(result)} {self.product['unit']} "
            f"({sign}{config.quantity(delta)})"
        )
        self.preview.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _save(self) -> None:
        self.clear_error()
        try:
            result = self.ctx.inventory.adjust(
                int(self.product["id"]),
                mode=self.mode,
                quantity=round(self.qty_spin.value(), 3),
                note=self.note_edit.toPlainText(),
                reference=self.reference_edit.text(),
            )
        except POSError as exc:
            self.show_error(exc.message)
            return
        self.result_data = result
        self.accept()
