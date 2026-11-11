from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos import __version__, config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import (
    Card,
    PageHeader,
    button,
    label,
    show_error,
    show_info,
)
from pos.ui.theme import DANGER, SUCCESS


class SettingsView(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = PageHeader(
            "Ajustes",
            "Datos del negocio para los comprobantes y mantenimiento de la base de datos.",
        )
        backup = button("Crear respaldo", "Primary")
        backup.clicked.connect(self._backup)
        header.add_action(backup)
        root.addWidget(header)

        columns = QHBoxLayout()
        columns.setSpacing(14)

        store_card = Card("Datos del negocio", "Se imprimen en el comprobante interno.")
        form = QFormLayout()
        form.setSpacing(9)
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(80)
        self.ruc_edit = QLineEdit()
        self.ruc_edit.setMaxLength(20)
        self.address_edit = QLineEdit()
        self.address_edit.setMaxLength(140)
        self.phone_edit = QLineEdit()
        self.phone_edit.setMaxLength(30)
        self.footer_edit = QPlainTextEdit()
        self.footer_edit.setFixedHeight(72)
        self.footer_edit.setPlaceholderText("Mensaje al pie del comprobante")
        form.addRow("Nombre del negocio", self.name_edit)
        form.addRow("RUC", self.ruc_edit)
        form.addRow("Dirección", self.address_edit)
        form.addRow("Teléfono", self.phone_edit)
        form.addRow("Pie del comprobante", self.footer_edit)
        store_card.body().addLayout(form)
        self.feedback_label = label("", "Hint")
        self.feedback_label.setVisible(False)
        store_card.body().addWidget(self.feedback_label)
        actions = QHBoxLayout()
        actions.addStretch(1)
        save_button = button("Guardar cambios", "Primary")
        save_button.clicked.connect(self._save)
        actions.addWidget(save_button)
        store_card.body().addLayout(actions)
        store_card.body().addStretch(1)
        columns.addWidget(store_card, 3)

        info_card = Card("Información del sistema", "Todo se guarda localmente en este equipo.")
        info_layout = QFormLayout()
        info_layout.setSpacing(10)
        version = label(f"Abarrotes POS v{__version__}", "FieldLabel")
        info_layout.addRow("Versión", version)
        path = label(str(self.ctx.db.path), "Muted")
        path.setWordWrap(True)
        path.setTextInteractionFlags(
            path.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info_layout.addRow("Base de datos", path)
        pdf_path = label(str(self.ctx.receipts.pdf_dir), "Muted")
        pdf_path.setWordWrap(True)
        pdf_path.setTextInteractionFlags(
            pdf_path.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info_layout.addRow("Boletas PDF", pdf_path)
        health_ok, _ = self.ctx.db.healthcheck()
        health = label("Conexión correcta" if health_ok else "Sin conexión", "FieldLabel")
        health.setStyleSheet(
            f"color: {SUCCESS if health_ok else DANGER};"
        )
        info_layout.addRow("Estado", health)
        info_card.body().addLayout(info_layout)

        folder_row = QHBoxLayout()
        open_folder = button("Abrir datos")
        open_folder.clicked.connect(self._open_data_folder)
        open_pdf_folder = button("Abrir boletas PDF")
        open_pdf_folder.clicked.connect(self._open_pdf_folder)
        folder_row.addWidget(open_folder)
        folder_row.addWidget(open_pdf_folder)
        folder_row.addStretch(1)
        info_card.body().addLayout(folder_row)

        backup_hint = QFrame()
        backup_hint.setObjectName("SoftPanel")
        hint_layout = QVBoxLayout(backup_hint)
        hint_layout.setContentsMargins(12, 10, 12, 10)
        hint_layout.setSpacing(4)
        hint_layout.addWidget(label("Copias de seguridad", "FieldLabel"))
        hint_text = label(
            "Guarda una copia del archivo SQLite en otra ubicación. "
            "Incluye productos, ventas, cajas y configuraciones.",
            "Hint",
        )
        hint_text.setWordWrap(True)
        hint_layout.addWidget(hint_text)
        info_card.body().addWidget(backup_hint)
        info_card.body().addStretch(1)
        columns.addWidget(info_card, 2)

        root.addLayout(columns, 1)
        root.addStretch(1)

    def refresh(self) -> None:
        info = self.ctx.settings.get_store_info()
        self.name_edit.setText(info.get("business_name", ""))
        self.ruc_edit.setText(info.get("ruc", ""))
        self.address_edit.setText(info.get("address", ""))
        self.phone_edit.setText(info.get("phone", ""))
        self.footer_edit.setPlainText(info.get("receipt_footer", ""))

    def _save(self) -> None:
        self.feedback_label.setVisible(False)
        try:
            self.ctx.settings.save(
                {
                    "business_name": self.name_edit.text(),
                    "ruc": self.ruc_edit.text(),
                    "address": self.address_edit.text(),
                    "phone": self.phone_edit.text(),
                    "receipt_footer": self.footer_edit.toPlainText(),
                }
            )
        except POSError as exc:
            self.feedback_label.setText(exc.message)
            self.feedback_label.setObjectName("ErrorLabel")
            self.feedback_label.setVisible(True)
            self.feedback_label.style().unpolish(self.feedback_label)
            self.feedback_label.style().polish(self.feedback_label)
            return
        self.feedback_label.setText("Ajustes guardados correctamente.")
        self.feedback_label.setObjectName("SuccessLabel")
        self.feedback_label.setVisible(True)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

    def _backup(self) -> None:
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suggested = str(Path(config.BACKUP_DIR) / f"pos-backup-{stamp}.db")
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar copia de seguridad",
            suggested,
            "Base de datos SQLite (*.db)",
        )
        if not destination:
            return
        try:
            saved = self.ctx.db.backup(destination)
        except Exception as exc:
            show_error(self, exc)
            return
        show_info(
            self,
            f"Copia de seguridad creada en:\n{saved}",
            "Respaldo completado",
        )

    def _open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ctx.db.path.parent)))

    def _open_pdf_folder(self) -> None:
        folder = self.ctx.receipts.pdf_dir
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
