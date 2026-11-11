from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget

from pos.ui.common import button, divider, label


class BaseDialog(QDialog):
    """Base con cabecera, cuerpo, mensaje de error y pie de acciones."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
        *,
        width: int = 520,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.setSizeGripEnabled(False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)

        self.title_label = label(title, "DialogTitle")
        root.addWidget(self.title_label)
        if subtitle:
            subtitle_label = label(subtitle, "DialogSubtitle")
            subtitle_label.setWordWrap(True)
            root.addWidget(subtitle_label)
        root.addWidget(divider())

        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        root.addLayout(self.body, 1)

        self.error_label = label("", "ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        root.addStretch(1)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)
        root.addLayout(self.footer)

    def add_cancel(self, text: str = "Cancelar") -> None:
        cancel = button(text)
        cancel.clicked.connect(self.reject)
        self.footer.addStretch(1)
        self.footer.addWidget(cancel)

    def add_primary(self, text: str = "Guardar") -> QWidget:
        primary = button(text, "Primary")
        primary.setDefault(True)
        primary.setAutoDefault(True)
        self.footer.addWidget(primary)
        return primary

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.setVisible(False)
