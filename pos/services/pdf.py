from __future__ import annotations

import html
import re
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import (
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QTextDocument,
)

from pos import config


def _safe(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _amount(value: int) -> str:
    return config.money(value)


def _display_status(sale: dict) -> str:
    cancelled = sale.get("status") == config.SALE_CANCELLED
    if cancelled:
        return (
            '<span style="color:#B4483F; font-weight:700;">ANULADA</span>'
        )
    return '<span style="color:#2E7A58; font-weight:700;">COMPLETADA</span>'


def build_sale_pdf_html(sale: dict, store: dict) -> str:
    """Construye una boleta estrecha para papel térmico."""
    items = []
    for item in sale.get("items", []):
        items.append(
            f"<p><b>{_safe(item.get('product_name'))}</b><br>"
            f"{_safe(config.quantity(item.get('quantity')))} "
            f"{_safe(item.get('unit', 'pieza'))} × {_amount(item.get('unit_price_cents', 0))}"
            f"<br>Importe: {_amount(item.get('line_total_cents', 0))}</p>"
        )
    discount = (f"<p>Descuento: -{_amount(sale.get('discount_cents', 0))}</p>"
                if int(sale.get('discount_cents', 0)) > 0 else "")
    cash = (f"<p>Recibido: {_amount(sale.get('cash_received_cents', 0))}<br>"
            f"Vuelto: {_amount(sale.get('change_cents', 0))}</p>"
            if sale.get('payment_method') == 'efectivo' else "")
    cancelled = (f"<p><b>ANULADA</b><br>{_safe(sale.get('cancel_reason') or 'Sin motivo registrado.')}</p>"
                 if sale.get('status') == config.SALE_CANCELLED else "")
    payment = config.PAYMENT_LABELS.get(sale.get('payment_method', ''), sale.get('payment_method', ''))
    return f"""<html><body style="font-family:Arial; font-size:9pt; color:black;">
    <p align="center"><b>{_safe(store.get('business_name', 'Abarrotes POS'))}</b><br>
    RUC: {_safe(store.get('ruc', ''))}<br>{_safe(store.get('address', ''))}<br>
    {_safe(store.get('phone', ''))}</p><hr>
    <p align="center"><b>COMPROBANTE DE VENTA</b><br>{_safe(sale.get('folio', ''))}<br>
    {_safe(config.format_datetime(sale.get('created_at')))}</p>
    <p>Caja: {_safe(sale.get('cash_session_id'))}<br>Pago: {_safe(payment)}<br>
    Estado: {_display_status(sale)}</p><hr>
    {''.join(items) or '<p>Esta venta no tiene líneas.</p>'}<hr>
    <p>Subtotal: {_amount(sale.get('subtotal_cents', 0))}</p>{discount}
    <p><b>TOTAL: {_amount(sale.get('total_cents', 0))}</b></p>{cash}{cancelled}<hr>
    <p align="center">{_safe(store.get('receipt_footer', ''))}</p>
    <p>Comprobante interno de venta. No constituye boleta ni factura electrónica SUNAT.</p>
    </body></html>"""


class ReceiptPdfService:
    """Genera y organiza los PDF de las ventas."""

    def __init__(self, pdf_dir: str | Path | None = None) -> None:
        self.pdf_dir = Path(pdf_dir or config.PDF_DIR).expanduser().resolve()

    def default_path(self, sale: dict) -> Path:
        local_date = config.to_local_datetime(sale.get("created_at")) or datetime.now()
        folio = re.sub(r"[^A-Za-z0-9_-]+", "_", str(sale.get("folio", "venta"))).strip("_")
        if not folio:
            folio = "venta"
        return self.pdf_dir / local_date.strftime("%Y") / local_date.strftime("%m") / f"{folio}.pdf"

    def generate(
        self,
        sale: dict,
        store: dict,
        destination: str | Path | None = None,
    ) -> Path:
        target = (
            Path(destination).expanduser().resolve()
            if destination
            else self.default_path(sale)
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(
            f".{target.stem}.{uuid.uuid4().hex[:8]}.tmp.pdf"
        )
        document = QTextDocument()
        try:
            document.setHtml(build_sale_pdf_html(sale, store))
            document.setDocumentMargin(0)
            writer = QPdfWriter(str(temporary))
            writer.setTitle(f"Comprobante de venta {sale.get('folio', '')}")
            writer.setCreator("Abarrotes POS")
            writer.setResolution(96)
            # Rollo de 80 mm, con altura calculada según el contenido.
            document.setTextWidth(76 * 96 / 25.4)
            height_mm = document.size().height() * 25.4 / 96 + 6
            writer.setPageSize(QPageSize(QSizeF(80, height_mm), QPageSize.Unit.Millimeter))
            writer.setPageMargins(QMarginsF(2, 2, 2, 2), QPageLayout.Unit.Millimeter)
            document.setPageSize(QSizeF(writer.width(), writer.height()))
            document.print_(writer)
            del writer
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise RuntimeError("El archivo PDF no se generó correctamente.")
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        return target
