from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import (
    confirm,
    label,
    money_spinbox,
)
from pos.ui.dialogs.base import BaseDialog
from pos.ui.theme import DANGER, SUCCESS, WARNING


class OpenCashDialog(BaseDialog):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        self.ctx = ctx
        self.result_data: dict | None = None
        super().__init__(
            "Abrir caja",
            "Registra el fondo con el que inicia el turno. Sin caja abierta no se pueden cobrar ventas.",
            parent,
            width=480,
        )
        self._build()
        self.add_cancel()
        primary = self.add_primary("Abrir caja")
        primary.clicked.connect(self._save)

    def _build(self) -> None:
        form = QGridLayout()
        form.setVerticalSpacing(5)
        form.addWidget(label("Fondo inicial", "FieldLabel"), 0, 0)
        self.amount_spin = money_spinbox(maximum=999999.99)
        form.addWidget(self.amount_spin, 1, 0)
        form.addWidget(label("Nota de apertura (opcional)", "FieldLabel"), 2, 0)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Ej. Turno mañana")
        self.notes_edit.setMaxLength(200)
        form.addWidget(self.notes_edit, 3, 0)
        self.body.addLayout(form)
        hint = label(
            "Cuenta el fondo antes de abrir. Este monto se sumará al efectivo esperado al cierre.",
            "Hint",
        )
        hint.setWordWrap(True)
        self.body.addWidget(hint)

    def _save(self) -> None:
        self.clear_error()
        try:
            self.result_data = self.ctx.cash.open(
                int(round(self.amount_spin.value() * 100)),
                self.notes_edit.text(),
            )
        except POSError as exc:
            self.show_error(exc.message)
            return
        self.accept()


class CashMovementDialog(BaseDialog):
    def __init__(self, ctx: AppContext, kind: str, parent: QWidget | None = None) -> None:
        if kind not in {"ingreso", "egreso"}:
            raise ValueError("Tipo de movimiento no válido")
        self.ctx = ctx
        self.kind = kind
        self.result_data: dict | None = None
        title = "Registrar ingreso" if kind == "ingreso" else "Registrar egreso"
        subtitle = (
            "Dinero que entra a la caja y no proviene de una venta."
            if kind == "ingreso"
            else "Dinero que sale de la caja, por ejemplo un gasto o retiro."
        )
        super().__init__(title, subtitle, parent, width=460)
        self._build()
        self.add_cancel()
        primary = self.add_primary(title)
        primary.clicked.connect(self._save)

    def _build(self) -> None:
        form = QGridLayout()
        form.setVerticalSpacing(5)
        form.addWidget(label("Monto", "FieldLabel"), 0, 0)
        self.amount_spin = money_spinbox(maximum=999999.99)
        form.addWidget(self.amount_spin, 1, 0)
        form.addWidget(label("Concepto", "FieldLabel"), 2, 0)
        self.concept_edit = QLineEdit()
        self.concept_edit.setPlaceholderText(
            "Ej. Compra de bolsas" if self.kind == "egreso" else "Ej. Fondo adicional"
        )
        self.concept_edit.setMaxLength(120)
        form.addWidget(self.concept_edit, 3, 0)
        self.body.addLayout(form)
        self.amount_spin.setFocus()

    def _save(self) -> None:
        self.clear_error()
        try:
            self.result_data = self.ctx.cash.add_movement(
                self.kind,
                int(round(self.amount_spin.value() * 100)),
                self.concept_edit.text(),
            )
        except POSError as exc:
            self.show_error(exc.message)
            return
        self.accept()


class CloseCashDialog(BaseDialog):
    def __init__(
        self, ctx: AppContext, summary: dict, parent: QWidget | None = None
    ) -> None:
        self.ctx = ctx
        self.summary = summary
        self.result_data: dict | None = None
        super().__init__(
            "Cerrar caja",
            "Cuenta el efectivo físico, ingrésalo y confirma el arqueo del turno.",
            parent,
            width=520,
        )
        self._build()
        self.add_cancel()
        primary = self.add_primary("Cerrar caja")
        primary.clicked.connect(self._save)

    def _build(self) -> None:
        breakdown = QFrame()
        breakdown.setObjectName("SoftPanel")
        layout = QGridLayout(breakdown)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(7)
        rows = (
            ("Fondo inicial", self.summary["opening_cash_cents"]),
            ("Ventas en efectivo", self.summary["cash_sales_cents"]),
            ("Ingresos manuales", self.summary["income_cents"]),
            ("Egresos", -self.summary["expense_cents"]),
            ("Devoluciones", -self.summary["refund_cents"]),
        )
        for index, (caption, amount) in enumerate(rows):
            layout.addWidget(label(caption, "Muted"), index, 0)
            value = label(config.money(amount), "FieldLabel")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(value, index, 1)
        layout.addWidget(label("Efectivo esperado", "FieldLabel"), len(rows), 0)
        expected = label(config.money(self.summary["expected_cash_cents"]), "MoneyBig")
        expected.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(expected, len(rows), 1)
        layout.setColumnStretch(0, 1)
        self.body.addWidget(breakdown)
        self.body.addWidget(label(
            f"Ventas por Yape (no son efectivo): {config.money(self.summary['yape_sales_cents'])}",
            "Muted",
        ))

        form = QGridLayout()
        form.setVerticalSpacing(5)
        form.addWidget(label("Efectivo contado", "FieldLabel"), 0, 0)
        self.counted_spin = money_spinbox(
            value_cents=int(self.summary["expected_cash_cents"]), maximum=999999.99
        )
        self.counted_spin.valueChanged.connect(self._update_difference)
        form.addWidget(self.counted_spin, 1, 0)
        self.difference_label = label("", "MoneyBig")
        self.difference_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        difference_box = QVBoxLayout()
        difference_box.setSpacing(3)
        difference_box.addWidget(label("Diferencia", "FieldLabel"))
        difference_box.addWidget(self.difference_label)
        form.addLayout(difference_box, 0, 1, 2, 1)
        form.setColumnStretch(0, 1)
        self.body.addLayout(form)

        form2 = QGridLayout()
        form2.setVerticalSpacing(5)
        form2.addWidget(label("Nota de cierre (opcional)", "FieldLabel"), 0, 0)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Observaciones del turno")
        self.notes_edit.setMaxLength(200)
        form2.addWidget(self.notes_edit, 1, 0)
        self.body.addLayout(form2)

        self.hint_label = label("", "Hint")
        self.hint_label.setWordWrap(True)
        self.body.addWidget(self.hint_label)
        self._update_difference()

    def _difference(self) -> int:
        counted = int(round(self.counted_spin.value() * 100))
        return counted - int(self.summary["expected_cash_cents"])

    def _update_difference(self) -> None:
        difference = self._difference()
        self.difference_label.setText(config.money(difference))
        if difference == 0:
            self.difference_label.setStyleSheet(f"color: {SUCCESS};")
            self.hint_label.setText("El arqueo coincide exactamente con lo esperado.")
            self.hint_label.setObjectName("Hint")
        elif difference < 0:
            self.difference_label.setStyleSheet(f"color: {DANGER};")
            self.hint_label.setText(
                "Falta efectivo respecto a lo esperado. La diferencia quedará registrada."
            )
            self.hint_label.setObjectName("WarningLabel")
        else:
            self.difference_label.setStyleSheet(f"color: {WARNING};")
            self.hint_label.setText(
                "Sobra efectivo respecto a lo esperado. La diferencia quedará registrada."
            )
            self.hint_label.setObjectName("WarningLabel")
        self.hint_label.style().unpolish(self.hint_label)
        self.hint_label.style().polish(self.hint_label)

    def _save(self) -> None:
        self.clear_error()
        difference = self._difference()
        if difference != 0:
            if not confirm(
                self,
                "Confirmar diferencia",
                f"El arqueo tiene una diferencia de {config.money(difference)}. "
                "¿Deseas cerrar la caja de todos modos?",
            ):
                return
        try:
            self.result_data = self.ctx.cash.close(
                int(round(self.counted_spin.value() * 100)),
                self.notes_edit.text(),
            )
        except POSError as exc:
            self.show_error(exc.message)
            return
        self.accept()
