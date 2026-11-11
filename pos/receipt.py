from __future__ import annotations

from pos import config

_LINE_WIDTH = 48


def _center(text: str, width: int = _LINE_WIDTH) -> str:
    text = text.strip()
    if len(text) >= width:
        return text[:width]
    return text.center(width)


def _pair(left: str, right: str, width: int = _LINE_WIDTH) -> str:
    space = width - len(left) - len(right)
    if space < 1:
        left = left[: max(0, width - len(right) - 1)]
        space = 1
    return f"{left}{' ' * space}{right}"


def build_receipt_text(sale: dict, store: dict) -> str:
    """Genera un comprobante interno en texto plano, de 48 columnas."""
    line = "-" * _LINE_WIDTH
    lines: list[str] = []
    lines.append(_center(store.get("business_name", "Abarrotes POS")))
    if store.get("ruc"):
        lines.append(_center(f"RUC: {store['ruc']}"))
    if store.get("address"):
        lines.append(_center(str(store["address"])[:_LINE_WIDTH]))
    if store.get("phone"):
        lines.append(_center(f"Tel.: {store['phone']}"))
    lines.append(line)
    lines.append(_center("COMPROBANTE INTERNO"))
    lines.append(f"Folio: {sale['folio']}")
    lines.append(f"Fecha: {config.format_datetime(sale['created_at'])}")
    lines.append(f"Caja: #{sale['cash_session_id']}")
    lines.append(
        f"Pago: {config.PAYMENT_LABELS.get(sale['payment_method'], sale['payment_method'])}"
    )
    lines.append(line)
    lines.append(_pair("Cant. / Descripción", "Importe"))
    lines.append(line)
    for item in sale.get("items", []):
        name = str(item["product_name"])
        if len(name) > _LINE_WIDTH:
            name = name[: _LINE_WIDTH - 1] + "…"
        lines.append(name)
        qty = f"{config.quantity(item['quantity'])} {item['unit']}"
        left = f"  {qty} x {config.money(item['unit_price_cents'])}"
        lines.append(_pair(left, config.money(item["line_total_cents"])))
    lines.append(line)
    lines.append(_pair("Subtotal", config.money(sale["subtotal_cents"])))
    if int(sale["discount_cents"]) > 0:
        lines.append(_pair("Descuento", f"-{config.money(sale['discount_cents'])}"))
    lines.append(_pair("TOTAL", config.money(sale["total_cents"])))
    if sale["payment_method"] == "efectivo":
        lines.append(_pair("Efectivo recibido", config.money(sale["cash_received_cents"])))
        lines.append(_pair("Vuelto", config.money(sale["change_cents"])))
    lines.append(line)
    lines.append(_center("Conserve este comprobante"))
    footer = str(store.get("receipt_footer", "")).strip()
    if footer:
        for footer_line in footer.splitlines():
            if footer_line.strip():
                lines.append(_center(footer_line.strip()))
    lines.append("")
    return "\n".join(lines)
