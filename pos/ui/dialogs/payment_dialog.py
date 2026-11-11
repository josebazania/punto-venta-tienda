from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QWidget,
)

from pos import config
from pos.ui.common import button, label, money_spinbox
from pos.ui.dialogs.base import BaseDialog
from pos.ui.theme import DANGER, PRIMARY


class PaymentDialog(BaseDialog):
    def __init__(self, subtotal_cents: int, parent: QWidget | None = None) -> None:
        self.subtotal_cents = max(0, int(subtotal_cents))
        self.result_data: dict | None = None
        super().__init__(
            "Cobrar venta",
            "Confirma el método de pago. El monto total se calcula automáticamente.",
            parent,
            width=520,
        )
        self._build()
        self.add_cancel("Volver al carrito")
        primary = self.add_primary("Registrar venta")
        primary.clicked.connect(self._accept)
        self._update_total()
        self.received_spin.setFocus()
        self.received_spin.selectAll()

    def _build(self) -> None:
        hero = QFrame()
        hero.setObjectName("SoftPanel")
        hero_layout = QGridLayout(hero)
        hero_layout.setContentsMargins(16, 12, 16, 12)
        hero_layout.setHorizontalSpacing(10)
        hero_layout.setVerticalSpacing(3)
        hero_layout.addWidget(label("Total a cobrar", "KpiLabel"), 0, 0)
        self.total_label = label(config.money(self.subtotal_cents), "TotalValue")
        hero_layout.addWidget(self.total_label, 1, 0)
        self.detail_label = label("", "Muted")
        self.detail_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        hero_layout.addWidget(self.detail_label, 0, 1, 2, 1)
        hero_layout.setColumnStretch(0, 1)
        self.body.addWidget(hero)

        payment_row = QHBoxLayout()
        method_box = QGridLayout()
        method_box.setVerticalSpacing(4)
        method_box.addWidget(label("Método de pago", "FieldLabel"), 0, 0)
        self.method_combo = QComboBox()
        for method in config.PAYMENT_METHODS:
            self.method_combo.addItem(config.PAYMENT_LABELS[method], method)
        self.method_combo.currentIndexChanged.connect(self._update_payment_panel)
        method_box.addWidget(self.method_combo, 1, 0)
        discount_box = QGridLayout()
        discount_box.setVerticalSpacing(4)
        discount_box.addWidget(label("Descuento", "FieldLabel"), 0, 0)
        self.discount_spin = money_spinbox(maximum=max(0.0, self.subtotal_cents / 100))
        self.discount_spin.valueChanged.connect(self._update_total)
        discount_box.addWidget(self.discount_spin, 1, 0)
        payment_row.addLayout(method_box, 1)
        payment_row.addLayout(discount_box, 1)
        self.body.addLayout(payment_row)

        self.cash_panel = QFrame()
        self.cash_panel.setObjectName("SoftPanel")
        cash_layout = QGridLayout(self.cash_panel)
        cash_layout.setContentsMargins(16, 12, 16, 12)
        cash_layout.setHorizontalSpacing(10)
        cash_layout.setVerticalSpacing(6)
        cash_layout.addWidget(label("Efectivo recibido", "FieldLabel"), 0, 0)
        self.received_spin = money_spinbox(
            value_cents=self.subtotal_cents, maximum=999999.99
        )
        self.received_spin.valueChanged.connect(self._update_change)
        cash_layout.addWidget(self.received_spin, 1, 0, 1, 2)

        quick = QHBoxLayout()
        quick.setSpacing(6)
        for text, cents in (
            ("Exacto", None),
            ("S/ 20", 2000),
            ("S/ 50", 5000),
            ("S/ 100", 10000),
        ):
            shortcut = button(text, "Small")
            shortcut.setCursor(Qt.PointingHandCursor)
            shortcut.clicked.connect(
                lambda checked=False, amount=cents: self._set_received(amount)
            )
            quick.addWidget(shortcut)
        quick.addStretch(1)
        cash_layout.addLayout(quick, 2, 0, 1, 2)

        cash_layout.addWidget(label("Vuelto", "FieldLabel"), 3, 0)
        self.change_label = label(config.money(0), "MoneyBig")
        self.change_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cash_layout.addWidget(self.change_label, 3, 1)
        cash_layout.setColumnStretch(0, 1)
        self.body.addWidget(self.cash_panel)

        self.hint_label = label(
            "El efectivo recibido debe cubrir el total para poder cobrar.",
            "Hint",
        )
        self.body.addWidget(self.hint_label)
        self.method_combo.setCurrentIndex(0)

    def _set_received(self, cents: int | None) -> None:
        if cents is None:
            cents = self._total_cents()
        self.received_spin.setValue(cents / 100)

    def _total_cents(self) -> int:
        discount = int(round(self.discount_spin.value() * 100))
        return max(0, self.subtotal_cents - discount)

    def _update_total(self) -> None:
        total = self._total_cents()
        self.total_label.setText(config.money(total))
        discount = self.subtotal_cents - total
        self.detail_label.setText(
            f"Subtotal {config.money(self.subtotal_cents)}"
            + (f"\nDescuento -{config.money(discount)}" if discount else "")
        )
        self.discount_spin.setMaximum(max(0.0, self.subtotal_cents / 100))
        if self.method_combo.currentData() == "efectivo":
            if self.received_spin.value() * 100 < total + 1:
                self.received_spin.setValue(total / 100)
        self._update_change()
        self._update_payment_panel()

    def _update_change(self) -> None:
        total = self._total_cents()
        received = int(round(self.received_spin.value() * 100))
        change = max(0, received - total)
        self.change_label.setText(config.money(change))
        if received < total:
            self.change_label.setStyleSheet(f"color: {DANGER}; font-weight: 700;")
            self.hint_label.setText("El efectivo recibido no cubre el total.")
            self.hint_label.setObjectName("ErrorLabel")
        else:
            self.change_label.setStyleSheet(f"color: {PRIMARY}; font-weight: 700;")
            self.hint_label.setText(
                "Entrega el vuelto indicado y cierra la venta."
                if change
                else "El efectivo coincide con el total."
            )
            self.hint_label.setObjectName("Hint")
        self.hint_label.style().unpolish(self.hint_label)
        self.hint_label.style().polish(self.hint_label)

    def _update_payment_panel(self) -> None:
        is_cash = self.method_combo.currentData() == "efectivo"
        self.cash_panel.setVisible(is_cash)
        if not is_cash:
            self.hint_label.setText(
                "Confirma el cobro cuando el pago haya sido aprobado."
            )

    def _accept(self) -> None:
        self.clear_error()
        method = self.method_combo.currentData()
        total = self._total_cents()
        discount = self.subtotal_cents - total
        received = int(round(self.received_spin.value() * 100)) if method == "efectivo" else 0
        if method == "efectivo" and received < total:
            self.show_error("El efectivo recibido no cubre el total de la venta.")
            return
        self.result_data = {
            "discount_cents": discount,
            "payment_method": method,
            "cash_received_cents": received,
        }
        self.accept()
