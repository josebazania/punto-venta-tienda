from __future__ import annotations

import logging
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.services.errors import POSError


# ----------------------------------------------------------------------
# Botones y etiquetas
# ----------------------------------------------------------------------
def button(text: str, role: str = "Secondary", parent: QWidget | None = None) -> QPushButton:
    widget = QPushButton(text, parent)
    widget.setObjectName(role)
    widget.setCursor(Qt.PointingHandCursor)
    return widget


def label(text: str = "", name: str = "", parent: QWidget | None = None) -> QLabel:
    widget = QLabel(text, parent)
    if name:
        widget.setObjectName(name)
    return widget


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def hline_spacer() -> QWidget:
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return spacer


# ----------------------------------------------------------------------
# Cabeceras y tarjetas
# ----------------------------------------------------------------------
class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.title_label = label(title, "PageTitle")
        self.subtitle_label = label(subtitle, "PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout, 1)
        self.subtitle_label.setVisible(bool(subtitle))
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout.addLayout(self.actions, 0)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget)
        return widget


class Card(QFrame):
    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
        *,
        margins: tuple[int, int, int, int] = (18, 16, 18, 16),
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*margins)
        self._layout.setSpacing(10)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.title_label = label(title, "SectionTitle")
        self.subtitle_label = label(subtitle, "Muted")
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(self.title_label)
        if subtitle:
            title_box.addWidget(self.subtitle_label)
        self.header.addLayout(title_box, 1)
        self._layout.addLayout(self.header)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add_header_widget(self, widget: QWidget) -> QWidget:
        self.header.addWidget(widget, 0, Qt.AlignRight)
        return widget


class KpiCard(QFrame):
    def __init__(
        self,
        caption: str,
        value: str = "—",
        hint: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        self.caption = label(caption, "KpiLabel")
        self.value = label(value, "KpiValue")
        self.hint = label(hint, "KpiHint")
        layout.addWidget(self.caption)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)
        self.hint.setVisible(bool(hint))
        layout.addStretch(1)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value.setText(value)
        if hint is not None:
            self.hint.setText(hint)
            self.hint.setVisible(bool(hint))


# ----------------------------------------------------------------------
# Tablas
# ----------------------------------------------------------------------
class DataTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSortingEnabled(False)

    def configure(self, headers: Iterable[str], widths: Iterable[int] | None = None) -> None:
        headers = list(headers)
        self.clearSpans()
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        widths_list = list(widths) if widths is not None else []
        for index, width in enumerate(widths_list):
            if index >= len(headers):
                break
            if width == 0:
                header.setSectionResizeMode(index, QHeaderView.Stretch)
            elif width < 0:
                header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
            else:
                self.setColumnWidth(index, width)
        if not widths_list:
            header.setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setDefaultSectionSize(38)

    def clear_rows(self) -> None:
        self.clearSpans()
        self.setRowCount(0)

    def show_empty(self, message: str = "No hay registros para mostrar.") -> None:
        self.clearSpans()
        self.setRowCount(1)
        item = QTableWidgetItem(message)
        item.setForeground(QColor("#8A948F"))
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        self.setItem(0, 0, item)
        if self.columnCount() > 1:
            self.setSpan(0, 0, 1, self.columnCount())
        self.setRowHeight(0, 48)

    def selected_id(self, column: int = 0) -> int | None:
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, column)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        return int(value) if value is not None else None

    def selected_row(self) -> int:
        return self.currentRow()


def table_item(
    text: object,
    *,
    align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter,
    color: str | None = None,
    bold: bool = False,
    data: object | None = None,
    tooltip: str | None = None,
) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    if color:
        item.setForeground(QColor(color))
    if bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    if data is not None:
        item.setData(Qt.UserRole, data)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def money_spinbox(
    value_cents: int = 0,
    *,
    maximum: float = 999999.99,
    parent: QWidget | None = None,
) -> QDoubleSpinBox:
    box = QDoubleSpinBox(parent)
    box.setDecimals(2)
    box.setRange(0.0, maximum)
    box.setSingleStep(1.0)
    box.setPrefix(f"{config.CURRENCY_SYMBOL} ")
    box.setGroupSeparatorShown(True)
    box.setValue(value_cents / 100)
    return box


def quantity_spinbox(
    value: float = 0.0,
    *,
    maximum: float = 9999.999,
    parent: QWidget | None = None,
) -> QDoubleSpinBox:
    box = QDoubleSpinBox(parent)
    box.setDecimals(3)
    box.setRange(0.0, maximum)
    box.setSingleStep(1.0)
    box.setGroupSeparatorShown(True)
    box.setValue(float(value))
    return box


def integer_spinbox(
    value: int = 0,
    *,
    minimum: int = 0,
    maximum: int = 999999,
    parent: QWidget | None = None,
) -> QSpinBox:
    box = QSpinBox(parent)
    box.setRange(minimum, maximum)
    box.setValue(value)
    return box


# ----------------------------------------------------------------------
# Mensajes
# ----------------------------------------------------------------------
def show_error(parent: QWidget | None, error: Exception) -> None:
    if isinstance(error, POSError):
        message = error.message
    else:
        logging.error("Error inesperado en la interfaz: %s", error, exc_info=True)
        message = (
            "Ocurrió un error inesperado. La operación no se completó.\n\n"
            f"Detalle: {error}"
        )
    QMessageBox.critical(parent, "No se pudo completar", message)


def show_info(parent: QWidget | None, message: str, title: str = "Listo") -> None:
    QMessageBox.information(parent, title, message)


def confirm(parent: QWidget | None, title: str, message: str) -> bool:
    result = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return result == QMessageBox.Yes


def dialog_accepted(dialog: QDialog) -> bool:
    """Ejecuta un diálogo modal y devuelve si fue aceptado.

    Se usa QDialog.DialogCode.Accepted explícitamente porque PySide6 no
    garantiza el alias ``dialog.Accepted`` en todas las versiones.
    """
    return dialog.exec() == QDialog.DialogCode.Accepted


def set_error(widget: QWidget, visible: bool = True) -> None:
    widget.setProperty("error", "true" if visible else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)
