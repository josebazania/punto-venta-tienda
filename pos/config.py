from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

APP_NAME = "Abarrotes POS"
APP_VERSION = "1.0.0"
ORGANIZATION = "Abarrotes"

BASE_DIR = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    # PyInstaller extrae el programa en una carpeta temporal; los datos deben
    # mantenerse fuera de ella entre ejecuciones.
    USER_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "AbarrotesPOS"
else:
    USER_DIR = BASE_DIR
DATA_DIR = USER_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = USER_DIR / "logs"

_env_db = os.environ.get("POS_DB_PATH", "").strip()
DB_PATH = Path(_env_db).expanduser() if _env_db else DATA_DIR / "pos.db"

_env_pdf = os.environ.get("POS_PDF_DIR", "").strip()
PDF_DIR = Path(_env_pdf).expanduser() if _env_pdf else DATA_DIR / "boletas"

CURRENCY_SYMBOL = "S/"
DEMO_DATA = os.environ.get("POS_SEED_DEMO", "1").strip().lower() not in {"0", "false", "no"}

UNITS = ("pieza", "kg", "litro", "paquete", "caja", "bolsa")
PAYMENT_METHODS = ("efectivo", "tarjeta", "transferencia", "yape")
PAYMENT_LABELS = {
    "efectivo": "Efectivo",
    "tarjeta": "Tarjeta",
    "transferencia": "Transferencia",
    "yape": "Yape",
}
SESSION_OPEN = "abierta"
SESSION_CLOSED = "cerrada"
SALE_COMPLETED = "completada"
SALE_CANCELLED = "anulada"

DEFAULT_SETTINGS = {
    "business_name": "Abarrotes La Esquina",
    "ruc": "20123456789",
    "address": "Av. Los Álamos 123 - Lima",
    "phone": "999 888 777",
    "receipt_footer": "¡Gracias por su compra!",
}

_CENTS = Decimal("0.01")
_MILLIS = Decimal("0.001")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_local_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def format_datetime(value: str | datetime | None, date_only: bool = False) -> str:
    dt = to_local_datetime(value)
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y" if date_only else "%d/%m/%Y %H:%M")


def format_time(value: str | datetime | None) -> str:
    dt = to_local_datetime(value)
    return "—" if dt is None else dt.strftime("%H:%M")


def format_long_date(value: datetime | None = None) -> str:
    dt = (value or utc_now()).astimezone()
    months = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    weekdays = (
        "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
    )
    return f"{weekdays[dt.weekday()]}, {dt.day} de {months[dt.month - 1]} de {dt.year}"


def money(cents: int | float | None) -> str:
    value = int(cents or 0)
    sign = "-" if value < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL} {abs(value) / 100:,.2f}"


def money_plain(cents: int | float | None) -> str:
    value = int(cents or 0)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 100:,.2f}"


def parse_money(value: str | int | float | None) -> int:
    """Convierte un monto escrito en soles a céntimos enteros."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP) * 100)
    text = str(value or "").strip()
    text = text.replace("S/", "").replace("s/", "").replace(" ", "")
    if not text:
        raise ValueError("Ingresa un monto.")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("El monto no es válido.") from exc
    if amount < 0:
        raise ValueError("El monto no puede ser negativo.")
    return int(amount.quantize(_CENTS, rounding=ROUND_HALF_UP) * 100)


def parse_quantity(value: str | int | float | None, *, allow_zero: bool = False) -> float:
    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("La cantidad no es válida.") from exc
    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError("La cantidad debe ser mayor que cero.")
    if amount != amount.quantize(_MILLIS):
        raise ValueError("La cantidad admite como máximo 3 decimales.")
    return float(amount)


def quantity(value: float | int | None) -> str:
    amount = Decimal(str(float(value or 0))).quantize(_MILLIS)
    text = format(amount, "f").rstrip("0").rstrip(".")
    return text or "0"


def line_total_cents(unit_price_cents: int, qty: float | Decimal) -> int:
    qty_decimal = qty if isinstance(qty, Decimal) else Decimal(str(qty))
    result = Decimal(int(unit_price_cents)) * qty_decimal
    return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def local_day(value: datetime | None = None) -> str:
    dt = (value or utc_now()).astimezone()
    return dt.strftime("%Y%m%d")


def status_label(value: str) -> str:
    return {
        SALE_COMPLETED: "Completada",
        SALE_CANCELLED: "Anulada",
        SESSION_OPEN: "Abierta",
        SESSION_CLOSED: "Cerrada",
    }.get(value, value)
