from __future__ import annotations

from pathlib import Path

from pos.db.database import Database
from pos.services.cash import CashService
from pos.services.inventory import InventoryService
from pos.services.pdf import ReceiptPdfService
from pos.services.products import ProductService
from pos.services.reports import ReportService
from pos.services.sales import SaleService
from pos.services.settings import SettingsService


class AppContext:
    """Contenedor de servicios compartidos por las vistas."""

    def __init__(self, db: Database, *, pdf_dir: str | Path | None = None) -> None:
        self.db = db
        self.products = ProductService(db)
        self.inventory = InventoryService(db)
        self.sales = SaleService(db)
        self.cash = CashService(db)
        self.reports = ReportService(db)
        self.settings = SettingsService(db)
        self.receipts = ReceiptPdfService(pdf_dir)
