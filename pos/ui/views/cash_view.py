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
    show_info,
    table_item,
)
from pos.ui.dialogs.cash_dialogs import (
    CashMovementDialog,
    CloseCashDialog,
    OpenCashDialog,
)
from pos.ui.theme import DANGER, SUCCESS, SUCCESS_SOFT, WARNING, WARNING_SOFT


class CashView(QWidget):
    data_changed = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.header = PageHeader(
            "Caja",
            "Apertura, movimientos y arqueo del turno actual.",
        )
        self.entry_button = button("Ingreso")
        self.entry_button.clicked.connect(lambda: self._movement("ingreso"))
        self.exit_button = button("Egreso")
        self.exit_button.clicked.connect(lambda: self._movement("egreso"))
        self.close_button = button("Cerrar caja", "Primary")
        self.close_button.clicked.connect(self._close_cash)
        self.header.add_action(self.entry_button)
        self.header.add_action(self.exit_button)
        self.header.add_action(self.close_button)
        root.addWidget(self.header)

        self.closed_card = Card("Caja cerrada", "Abre un turno para comenzar a vender.")
        closed_body = QHBoxLayout()
        closed_body.setSpacing(18)
        icon = label("◉", "Logo")
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"background: {WARNING_SOFT}; color: {WARNING}; "
            "border-radius: 28px; font-size: 22pt;"
        )
        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        text_box.addWidget(label("No hay una caja abierta", "SectionTitle"))
        description = label(
            "Registra el fondo inicial del turno. Mientras la caja esté cerrada "
            "el punto de venta no permitirá cobrar.",
            "Muted",
        )
        description.setWordWrap(True)
        text_box.addWidget(description)
        closed_body.addWidget(icon)
        closed_body.addLayout(text_box, 1)
        open_button = button("Abrir caja", "Primary")
        open_button.clicked.connect(self.open_cash)
        closed_body.addWidget(open_button)
        self.closed_card.body().addLayout(closed_body)
        root.addWidget(self.closed_card)

        self.open_panel = QWidget()
        open_layout = QVBoxLayout(self.open_panel)
        open_layout.setContentsMargins(0, 0, 0, 0)
        open_layout.setSpacing(14)

        session_row = QHBoxLayout()
        self.session_label = label("", "SectionTitle")
        self.session_status = label("Turno en curso", "Pill")
        self.session_status.setStyleSheet(
            f"background: {SUCCESS_SOFT}; color: {SUCCESS}; "
            "border-radius: 10px; padding: 4px 10px; font-weight: 600;"
        )
        session_row.addWidget(self.session_label)
        session_row.addWidget(self.session_status)
        session_row.addStretch(1)
        open_layout.addLayout(session_row)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(14)
        self.opening_kpi = KpiCard("Fondo inicial", "S/ 0.00")
        self.cash_sales_kpi = KpiCard("Ventas en efectivo", "S/ 0.00", "0 ventas")
        self.movements_kpi = KpiCard("Movimientos manuales", "S/ 0.00")
        self.expected_kpi = KpiCard("Efectivo esperado", "S/ 0.00", "al cierre del turno")
        for index, widget in enumerate(
            (
                self.opening_kpi,
                self.cash_sales_kpi,
                self.movements_kpi,
                self.expected_kpi,
            )
        ):
            kpis.addWidget(widget, 0, index)
            kpis.setColumnStretch(index, 1)
        open_layout.addLayout(kpis)

        movements_card = Card(
            "Movimientos de la caja",
            "Ingresos, egresos y devoluciones registrados en este turno.",
        )
        self.movements_table = DataTable()
        self.movements_table.configure(
            ("Hora", "Tipo", "Concepto", "Venta", "Monto"),
            (80, 120, 0, 140, 130),
        )
        self.movements_table.setMinimumHeight(190)
        movements_card.body().addWidget(self.movements_table)
        open_layout.addWidget(movements_card, 1)
        root.addWidget(self.open_panel, 1)

        history_card = Card("Historial de cajas", "Turnos cerrados y diferencias de arqueo.")
        self.history_table = DataTable()
        self.history_table.configure(
            (
                "Caja",
                "Apertura",
                "Cierre",
                "Fondo",
                "Esperado",
                "Contado",
                "Diferencia",
                "Ventas",
            ),
            (60, 128, 128, 92, 92, 92, 92, 0),
        )
        self.history_table.setMinimumHeight(140)
        history_card.body().addWidget(self.history_table)
        root.addWidget(history_card)

    def refresh(self) -> None:
        try:
            summary = self.ctx.cash.current()
            history = self.ctx.cash.history(limit=30)
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return

        is_open = summary is not None
        self.closed_card.setVisible(not is_open)
        self.open_panel.setVisible(is_open)
        self.entry_button.setVisible(is_open)
        self.exit_button.setVisible(is_open)
        self.close_button.setVisible(is_open)

        if summary:
            self.session_label.setText(
                f"Caja #{summary['id']} · abierta {config.format_datetime(summary['opened_at'])}"
            )
            self.opening_kpi.set_value(config.money(summary["opening_cash_cents"]))
            self.cash_sales_kpi.set_value(
                config.money(summary["cash_sales_cents"]),
                f"{summary['cash_sales_count']} ventas",
            )
            net_movements = summary["income_cents"] - summary["expense_cents"]
            self.movements_kpi.set_value(
                config.money(net_movements),
                f"+{config.money(summary['income_cents'])} / "
                f"-{config.money(summary['expense_cents'])}",
            )
            self.expected_kpi.set_value(
                config.money(summary["expected_cash_cents"]),
                "incluye devoluciones" if summary["refund_cents"] else "al cierre del turno",
            )
            self._load_movements(summary)

        self.history_table.clear_rows()
        closed_sessions = [session for session in history if session["status"] == config.SESSION_CLOSED]
        for session in closed_sessions:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(
                row, 0, table_item(f"#{session['id']}", align=Qt.AlignLeft | Qt.AlignVCenter)
            )
            self.history_table.setItem(
                row, 1, table_item(config.format_datetime(session["opened_at"]))
            )
            self.history_table.setItem(
                row, 2, table_item(config.format_datetime(session["closed_at"]))
            )
            self.history_table.setItem(
                row,
                3,
                table_item(
                    config.money(session["opening_cash_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.history_table.setItem(
                row,
                4,
                table_item(
                    config.money(session["expected_cash_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.history_table.setItem(
                row,
                5,
                table_item(
                    config.money(session["counted_cash_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            difference = int(session["difference_cents"] or 0)
            self.history_table.setItem(
                row,
                6,
                table_item(
                    config.money(difference),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=SUCCESS if difference == 0 else DANGER,
                    bold=True,
                ),
            )
            self.history_table.setItem(
                row,
                7,
                table_item(
                    config.money(session["sales_total_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
        if self.history_table.rowCount() == 0:
            self.history_table.show_empty("Aún no hay cajas cerradas.")

    def _load_movements(self, summary: dict) -> None:
        self.movements_table.clear_rows()
        try:
            movements = self.ctx.cash.movements(int(summary["id"]))
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        kinds = {"ingreso": "Ingreso", "egreso": "Egreso", "devolucion": "Devolución"}
        for movement in movements:
            row = self.movements_table.rowCount()
            self.movements_table.insertRow(row)
            self.movements_table.setItem(
                row, 0, table_item(config.format_time(movement["created_at"]))
            )
            kind = str(movement["kind"])
            self.movements_table.setItem(
                row,
                1,
                table_item(
                    kinds.get(kind, kind),
                    color=DANGER if kind in {"egreso", "devolucion"} else SUCCESS,
                ),
            )
            self.movements_table.setItem(row, 2, table_item(movement["concept"]))
            self.movements_table.setItem(
                row, 3, table_item(movement.get("sale_folio") or "—")
            )
            signed = (
                -int(movement["amount_cents"])
                if kind in {"egreso", "devolucion"}
                else int(movement["amount_cents"])
            )
            self.movements_table.setItem(
                row,
                4,
                table_item(
                    f"{'+' if signed > 0 else ''}{config.money(signed)}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=SUCCESS if signed > 0 else DANGER,
                    bold=True,
                ),
            )
        for row in range(self.movements_table.rowCount()):
            self.movements_table.setRowHeight(row, 36)
        if self.movements_table.rowCount() == 0:
            self.movements_table.show_empty(
                "No hay ingresos, egresos ni devoluciones en este turno."
            )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def open_cash(self) -> None:
        dialog = OpenCashDialog(self.ctx, self)
        if dialog_accepted(dialog) and dialog.result_data:
            self.refresh()
            self.data_changed.emit()

    def _movement(self, kind: str) -> None:
        try:
            if self.ctx.cash.current() is None:
                show_error(self, POSError("Abre la caja antes de registrar movimientos."))
                return
            dialog = CashMovementDialog(self.ctx, kind, self)
        except POSError as exc:
            show_error(self, exc)
            return
        if dialog_accepted(dialog) and dialog.result_data:
            self.refresh()
            self.data_changed.emit()

    def _close_cash(self) -> None:
        try:
            summary = self.ctx.cash.current()
            if summary is None:
                show_error(self, POSError("No hay una caja abierta."))
                return
            dialog = CloseCashDialog(self.ctx, summary, self)
        except POSError as exc:
            show_error(self, exc)
            return
        if dialog_accepted(dialog) and dialog.result_data:
            closed = dialog.result_data
            difference = int(closed.get("difference_cents") or 0)
            self.refresh()
            self.data_changed.emit()
            show_info(
                self,
                f"La caja #{closed['id']} se cerró correctamente.\n"
                f"Diferencia del arqueo: {config.money(difference)}.",
                "Caja cerrada",
            )
