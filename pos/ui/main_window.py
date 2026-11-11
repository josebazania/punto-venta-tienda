from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.ui.common import button, label
from pos.ui.views.cash_view import CashView
from pos.ui.views.dashboard_view import DashboardView
from pos.ui.views.history_view import HistoryView
from pos.ui.views.inventory_view import InventoryView
from pos.ui.views.products_view import ProductsView
from pos.ui.views.sale_view import SaleView
from pos.ui.views.settings_view import SettingsView
from pos.ui.views.statistics_view import StatisticsView

_NAV_ITEMS = (
    ("Inicio", "⌂"),
    ("Punto de venta", "🛒"),
    ("Productos", "◫"),
    ("Inventario", "▤"),
    ("Ventas", "≡"),
    ("Caja", "◉"),
    ("Ajustes", "⚙"),
    ("Estadísticas", "▥"),
)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{config.APP_NAME} · Punto de venta")
        self.resize(1360, 840)
        self.setMinimumSize(1120, 700)
        self._build()
        self._connect_signals()
        self._update_cash_badge()
        self.navigate(0)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView(self.ctx)
        self.sale_view = SaleView(self.ctx)
        self.products_view = ProductsView(self.ctx)
        self.inventory_view = InventoryView(self.ctx)
        self.history_view = HistoryView(self.ctx)
        self.cash_view = CashView(self.ctx)
        self.settings_view = SettingsView(self.ctx)
        self.statistics_view = StatisticsView(self.ctx)
        self.views = [
            self.dashboard_view,
            self.sale_view,
            self.products_view,
            self.inventory_view,
            self.history_view,
            self.cash_view,
            self.settings_view,
            self.statistics_view,
        ]
        for view in self.views:
            self.stack.addWidget(view)
        main_layout.addWidget(self.stack, 1)
        layout.addWidget(main_area, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(7)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = label("A", "Logo")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignCenter)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(label("Abarrotes POS", "BrandTitle"))
        brand_text.addWidget(label("TIENDA DE BARRIO", "BrandSub"))
        brand.addLayout(brand_text)
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(20)

        caption = label("OPERACIÓN", "NavCaption")
        layout.addWidget(caption)
        layout.addSpacing(2)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, (text, icon) in enumerate(_NAV_ITEMS):
            nav = QPushButton(f"{icon}   {text}")
            nav.setObjectName("NavButton")
            nav.setCheckable(True)
            nav.setCursor(Qt.PointingHandCursor)
            nav.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            self.nav_group.addButton(nav, index)
            self.nav_buttons.append(nav)
            layout.addWidget(nav)

        layout.addStretch(1)
        line = QFrame()
        line.setObjectName("SidebarLine")
        line.setFixedHeight(1)
        layout.addWidget(line)
        layout.addSpacing(8)
        layout.addWidget(label("SQLite · datos locales", "SidebarFooter"))
        layout.addWidget(label(f"Versión {config.APP_VERSION}", "SidebarFooter"))
        return sidebar

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar.setFixedHeight(64)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(14)

        self.date_label = label(config.format_long_date().capitalize(), "TopbarDate")
        layout.addWidget(self.date_label)
        layout.addStretch(1)

        refresh = button("Actualizar", "Ghost")
        refresh.clicked.connect(self._refresh_current)
        layout.addWidget(refresh)

        self.clock_label = label("", "TopbarTime")
        layout.addWidget(self.clock_label)

        self.cash_badge = QPushButton("● Caja cerrada")
        self.cash_badge.setObjectName("CashBadge")
        self.cash_badge.setProperty("state", "closed")
        self.cash_badge.setCursor(Qt.PointingHandCursor)
        self.cash_badge.clicked.connect(self._go_to_cash)
        layout.addWidget(self.cash_badge)
        return topbar

    # ------------------------------------------------------------------
    # Señales y navegación
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.dashboard_view.new_sale_requested.connect(lambda: self.navigate(1))
        self.dashboard_view.cash_requested.connect(self._go_to_cash)
        self.dashboard_view.history_requested.connect(lambda: self.navigate(4))
        self.dashboard_view.inventory_requested.connect(lambda: self.navigate(3))
        self.sale_view.cash_requested.connect(self._go_to_cash)
        for view in (
            self.sale_view,
            self.products_view,
            self.inventory_view,
            self.history_view,
            self.cash_view,
        ):
            view.data_changed.connect(self._on_data_changed)

    def navigate(self, index: int) -> None:
        if not 0 <= index < len(self.views):
            return
        self.stack.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        view = self.views[index]
        refresher = getattr(view, "refresh", None) or getattr(view, "refresh_data", None)
        if callable(refresher):
            refresher()
        self._update_cash_badge()

    def _go_to_cash(self) -> None:
        self.navigate(5)
        if self.ctx.cash.current() is None:
            QTimer.singleShot(0, self.cash_view.open_cash)

    def _refresh_current(self) -> None:
        view = self.stack.currentWidget()
        refresher = getattr(view, "refresh", None) or getattr(view, "refresh_data", None)
        if callable(refresher):
            refresher()
        self._update_cash_badge()

    def _on_data_changed(self) -> None:
        self._update_cash_badge()

    def _update_cash_badge(self) -> None:
        try:
            session = self.ctx.cash.current()
        except Exception:  # pragma: no cover - defensivo
            session = None
        if session:
            text = f"● Caja abierta · {config.money(session['expected_cash_cents'])}"
            state = "open"
        else:
            text = "● Caja cerrada"
            state = "closed"
        self.cash_badge.setText(text)
        self.cash_badge.setProperty("state", state)
        self.cash_badge.style().unpolish(self.cash_badge)
        self.cash_badge.style().polish(self.cash_badge)

    def _update_clock(self) -> None:
        from datetime import datetime

        self.clock_label.setText(datetime.now().strftime("%H:%M"))
        self.date_label.setText(config.format_long_date().capitalize())

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - API de Qt
        try:
            logging.getLogger(__name__).info("Cerrando la aplicación")
        finally:
            super().closeEvent(event)


def build_icon() -> QIcon:
    return QIcon(str(Path(__file__).resolve().parent / "assets" / "icono.png"))


def configure_logging() -> None:
    from logging.handlers import RotatingFileHandler

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        config.LOG_DIR / "pos.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.ORGANIZATION)
    app.setWindowIcon(build_icon())
    from pos.ui.theme import apply_theme

    apply_theme(app)

    from pos.db.database import Database

    try:
        db = Database(demo_data=config.DEMO_DATA)
    except Exception as exc:  # pragma: no cover - depende del sistema de archivos
        logging.exception("No se pudo abrir la base de datos")
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None,
            "No se pudo iniciar",
            "No fue posible abrir la base de datos.\n\n"
            f"{exc}\n\nRevisa los permisos de la carpeta data/.",
        )
        return 1

    context = AppContext(db)
    window = MainWindow(context)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
