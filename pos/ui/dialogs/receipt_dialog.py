from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.receipt import build_receipt_text
from pos.services.pdf import ReceiptPdfService
from pos.ui.common import button, label, show_error, show_info
from pos.ui.dialogs.base import BaseDialog


class ReceiptDialog(BaseDialog):
    def __init__(
        self,
        sale: dict,
        store: dict,
        parent: QWidget | None = None,
        *,
        pdf_path: str | Path | None = None,
        pdf_service: ReceiptPdfService | None = None,
    ) -> None:
        self.sale = sale
        self.store = store
        self.receipt_text = build_receipt_text(sale, store)
        self.pdf_path = Path(pdf_path) if pdf_path else None
        self.pdf_service = pdf_service
        super().__init__(
            "Venta registrada",
            f"Folio {sale['folio']} · {config.money(sale['total_cents'])}",
            parent,
            width=500,
        )
        self._build()
        self.resize(500, 690)
        printer_button = button("Imprimir comprobante")
        printer_button.clicked.connect(self._print)
        self.footer.addStretch(1)
        self.footer.addWidget(printer_button)
        close = button("Nueva venta", "Primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        self.footer.addWidget(close)

    def _build(self) -> None:
        panel = QFrame()
        panel.setObjectName("SoftPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        self.viewer = QPlainTextEdit()
        self.viewer.setObjectName("ReceiptViewer")
        self.viewer.setReadOnly(True)
        self.viewer.setPlainText(self.receipt_text)
        self.viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Cascadia Mono", 9)
        font.setStyleHint(QFont.Monospace)
        self.viewer.setFont(font)
        self.viewer.setStyleSheet(
            "QPlainTextEdit#ReceiptViewer {"
            " background: #FFFFFF; border: none; padding: 14px; min-height: 0;"
            "}"
        )
        self.viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel_layout.addWidget(self.viewer)
        panel.setFixedHeight(420)
        self.body.addWidget(panel)
        hint = label(
            "Para la ticketera térmica usa «Imprimir comprobante». "
            "El PDF está preparado para papel térmico de 80 mm.",
            "Hint",
        )
        hint.setWordWrap(True)
        self.body.addWidget(hint)

        pdf_row = QHBoxLayout()
        pdf_row.setSpacing(8)
        self.pdf_label = label("", "Tiny")
        self.pdf_label.setWordWrap(True)
        pdf_row.addWidget(self.pdf_label, 1)
        self.open_pdf_button = button("Abrir PDF", "Link")
        self.open_pdf_button.clicked.connect(self._open_pdf)
        self.save_pdf_button = button("Guardar copia", "Link")
        self.save_pdf_button.clicked.connect(self._save_pdf_as)
        pdf_row.addWidget(self.open_pdf_button)
        pdf_row.addWidget(self.save_pdf_button)
        self.body.addLayout(pdf_row)
        self._update_pdf_status()

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def _service(self) -> ReceiptPdfService:
        if self.pdf_service is None:
            self.pdf_service = ReceiptPdfService()
        return self.pdf_service

    def _update_pdf_status(self) -> None:
        exists = self.pdf_path is not None and self.pdf_path.exists()
        if exists and self.pdf_path is not None:
            self.pdf_label.setText(f"PDF listo: {self.pdf_path.name}")
            self.pdf_label.setToolTip(str(self.pdf_path))
            self.open_pdf_button.setVisible(True)
        elif self.pdf_path is not None:
            self.pdf_label.setText("El PDF no se encontró. Puedes generarlo nuevamente.")
            self.pdf_label.setToolTip(str(self.pdf_path))
            self.open_pdf_button.setVisible(True)
        else:
            self.pdf_label.setText("PDF pendiente. Puedes generarlo con «Abrir PDF».")
            self.pdf_label.setToolTip("")
            self.open_pdf_button.setVisible(True)

    def _generate_default(self) -> Path | None:
        try:
            path = self._service().generate(self.sale, self.store)
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return None
        self.pdf_path = path
        self._update_pdf_status()
        return path

    def _open_pdf(self) -> None:
        path = self.pdf_path
        if path is None or not path.exists():
            path = self._generate_default()
        if path is None:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            show_info(self, f"No se pudo abrir el visor PDF.\n\n{path}", "PDF generado")

    def _save_pdf_as(self) -> None:
        try:
            initial = self.pdf_path or self._service().default_path(self.sale)
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar boleta PDF",
            str(initial),
            "Documento PDF (*.pdf)",
        )
        if not destination:
            return
        target = Path(destination)
        if not target.suffix:
            target = target.with_suffix(".pdf")
        try:
            saved = self._service().generate(self.sale, self.store, target)
        except Exception as exc:
            show_error(self, exc)
            return
        self.pdf_path = saved
        self._update_pdf_status()
        show_info(self, f"Boleta PDF guardada en:\n{saved}", "PDF guardado")

    # ------------------------------------------------------------------
    # Impresión térmica
    # ------------------------------------------------------------------
    def _print(self) -> None:
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            document = QTextDocument()
            font = QFont("Consolas", 9)
            document.setDefaultFont(font)
            document.setPlainText(self.receipt_text)
            if hasattr(document, "print_"):
                document.print_(printer)
            else:  # pragma: no cover - compatibilidad entre versiones
                document.print(printer)
        except Exception as exc:  # pragma: no cover - depende de la impresora
            show_error(self, exc)
