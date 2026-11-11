from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Paleta de la aplicación -------------------------------------------------
BG = "#F5F3EE"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#FBFAF6"
SIDEBAR = "#15352E"
SIDEBAR_ACTIVE = "#29584C"
SIDEBAR_TEXT = "#D6E3DE"
SIDEBAR_MUTED = "#8FAEA6"
PRIMARY = "#1F6F5C"
PRIMARY_DARK = "#175747"
PRIMARY_SOFT = "#E7F1ED"
TEXT = "#1E2A26"
MUTED = "#6F7B76"
BORDER = "#E2DED4"
DANGER = "#B4483F"
DANGER_SOFT = "#FAECEA"
WARNING = "#A66E12"
WARNING_SOFT = "#FCF3E1"
SUCCESS = "#2E7A58"
SUCCESS_SOFT = "#E8F4ED"
ACCENT = "#E0A84A"
TABLE_ALT = "#FAF8F2"
SELECTION = "#E8F1EC"


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(SURFACE))
    palette.setColor(QPalette.AlternateBase, QColor(TABLE_ALT))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(SURFACE))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipBase, QColor(TEXT))
    palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    outline: none;
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-size: 10pt;
}}
QToolTip {{
    background: {TEXT};
    color: #FFFFFF;
    border: none;
    padding: 6px 8px;
    border-radius: 4px;
}}

/* ---------------- Barra lateral ---------------- */
QFrame#Sidebar {{
    background: {SIDEBAR};
    border: none;
}}
QLabel#Logo {{
    background: {ACCENT};
    color: {SIDEBAR};
    border-radius: 18px;
    font-size: 16pt;
    font-weight: 800;
}}
QLabel#BrandTitle {{
    color: #FFFFFF;
    font-size: 12pt;
    font-weight: 700;
}}
QLabel#BrandSub {{
    color: {SIDEBAR_MUTED};
    font-size: 8.5pt;
    letter-spacing: 1px;
}}
QPushButton#NavButton {{
    background: transparent;
    color: {SIDEBAR_TEXT};
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-size: 10pt;
}}
QPushButton#NavButton:hover {{
    background: #1E443B;
    color: #FFFFFF;
}}
QPushButton#NavButton:checked {{
    background: {SIDEBAR_ACTIVE};
    color: #FFFFFF;
    font-weight: 600;
}}
QLabel#NavCaption {{
    color: {SIDEBAR_MUTED};
    font-size: 8pt;
    letter-spacing: 1.5px;
    font-weight: 600;
}}
QLabel#SidebarFooter {{
    color: {SIDEBAR_MUTED};
    font-size: 8.5pt;
}}
QFrame#SidebarLine {{
    background: #2B4A42;
    border: none;
    max-height: 1px;
}}

/* ---------------- Barra superior ---------------- */
QFrame#Topbar {{
    background: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QLabel#TopbarDate {{
    color: {MUTED};
    font-size: 9.5pt;
}}
QLabel#TopbarTime {{
    color: {TEXT};
    font-size: 11pt;
    font-weight: 600;
}}
QPushButton#CashBadge {{
    border: none;
    border-radius: 14px;
    padding: 6px 14px;
    font-size: 9pt;
    font-weight: 600;
}}
QPushButton#CashBadge[state="open"] {{
    background: {SUCCESS_SOFT};
    color: {SUCCESS};
}}
QPushButton#CashBadge[state="closed"] {{
    background: {WARNING_SOFT};
    color: {WARNING};
}}
QPushButton#CashBadge:hover {{
    border: 1px solid {BORDER};
}}

/* ---------------- Títulos y tarjetas ---------------- */
QLabel#PageTitle {{
    font-size: 22pt;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#PageSubtitle {{
    color: {MUTED};
    font-size: 9.5pt;
}}
QFrame#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#KpiCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#KpiLabel {{
    color: {MUTED};
    font-size: 9pt;
    font-weight: 500;
}}
QLabel#KpiValue {{
    color: {TEXT};
    font-size: 21pt;
    font-weight: 700;
}}
QLabel#KpiHint {{
    color: {MUTED};
    font-size: 8.5pt;
}}
QLabel#SectionTitle {{
    font-size: 11pt;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#Muted {{
    color: {MUTED};
    font-size: 9pt;
}}
QLabel#Tiny {{
    color: {MUTED};
    font-size: 8.5pt;
}}
QLabel#TotalValue {{
    color: {PRIMARY};
    font-size: 27pt;
    font-weight: 800;
}}
QLabel#MoneyBig {{
    color: {TEXT};
    font-size: 16pt;
    font-weight: 700;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 8.5pt;
}}
QLabel#ErrorLabel {{
    color: {DANGER};
    font-size: 9pt;
    background: {DANGER_SOFT};
    border-radius: 6px;
    padding: 6px 8px;
}}
QLabel#SuccessLabel {{
    color: {SUCCESS};
    background: {SUCCESS_SOFT};
    border-radius: 6px;
    padding: 6px 8px;
}}
QLabel#WarningLabel {{
    color: {WARNING};
    background: {WARNING_SOFT};
    border-radius: 6px;
    padding: 6px 8px;
}}
QLabel#Pill {{
    color: {MUTED};
    background: {BG};
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 8.5pt;
    font-weight: 600;
}}
QFrame#Divider {{
    background: {BORDER};
    border: none;
    max-height: 1px;
}}
QFrame#Ticket {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#SoftPanel {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* ---------------- Botones ---------------- */
QPushButton {{
    min-height: 24px;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 9.5pt;
    font-weight: 600;
}}
QPushButton#Primary {{
    background: {PRIMARY};
    color: #FFFFFF;
    border: 1px solid {PRIMARY};
}}
QPushButton#Primary:hover {{
    background: {PRIMARY_DARK};
    border-color: {PRIMARY_DARK};
}}
QPushButton#Primary:pressed {{
    background: #123F35;
}}
QPushButton#Secondary {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid #D5D0C5;
}}
QPushButton#Secondary:hover {{
    background: #F7F5EF;
    border-color: #BEB8AB;
}}
QPushButton#Danger {{
    background: {DANGER_SOFT};
    color: {DANGER};
    border: 1px solid #EFCFCB;
}}
QPushButton#Danger:hover {{
    background: #F6DDDA;
}}
QPushButton#Ghost {{
    background: transparent;
    color: {PRIMARY};
    border: none;
    padding: 6px 8px;
}}
QPushButton#Ghost:hover {{
    background: {PRIMARY_SOFT};
}}
QPushButton#Link {{
    background: transparent;
    color: {MUTED};
    border: none;
    padding: 4px;
    font-size: 9pt;
}}
QPushButton#Link:hover {{
    color: {PRIMARY};
}}
QPushButton#Small {{
    min-height: 20px;
    padding: 4px 9px;
    font-size: 8.5pt;
    border-radius: 6px;
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {TEXT};
}}
QPushButton#Small:hover {{
    background: {BG};
}}
QPushButton#Checkout {{
    background: {PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    min-height: 48px;
    font-size: 12pt;
    font-weight: 700;
}}
QPushButton#Checkout:hover {{
    background: {PRIMARY_DARK};
}}
QPushButton:disabled {{
    background: #ECE9E1;
    color: #A6A19A;
    border-color: #E2DED4;
}}
QPushButton#NavButton:disabled {{
    background: transparent;
    color: #5E7B73;
}}

/* ---------------- Formularios ---------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{
    background: {SURFACE};
    border: 1px solid #D8D3C8;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 24px;
    selection-background-color: {PRIMARY};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {PRIMARY};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QDateEdit:disabled {{
    background: #F1EEE7;
    color: #8E8A82;
}}
QLineEdit[error="true"] {{
    border: 1px solid {DANGER};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 24px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url("{_ASSETS_DIR.as_posix()}/chevron-down.svg");
    width: 10px;
    height: 6px;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0;
    height: 0;
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT};
    padding: 4px;
}}
QCheckBox {{
    spacing: 7px;
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #BEB8AB;
    border-radius: 4px;
    background: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
    image: url("{_ASSETS_DIR.as_posix()}/check.svg");
}}
QFormLayout QLabel {{
    color: #3E4A45;
    font-size: 9.5pt;
}}
QLabel#FieldLabel {{
    color: #3E4A45;
    font-size: 9.5pt;
    font-weight: 500;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 12px;
    padding: 14px;
    font-weight: 600;
    background: {SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {MUTED};
}}

/* ---------------- Tablas ---------------- */
QTableWidget, QTableView {{
    background: {SURFACE};
    alternate-background-color: {TABLE_ALT};
    border: none;
    gridline-color: transparent;
    selection-background-color: {SELECTION};
    selection-color: {TEXT};
    font-size: 9.5pt;
}}
QTableWidget::item {{
    padding: 7px 8px;
    border: none;
    border-bottom: 1px solid #F1EEE7;
}}
QTableWidget::item:selected {{
    background: {SELECTION};
    color: {TEXT};
}}
QHeaderView {{
    background: transparent;
    border: none;
}}
QHeaderView::section {{
    background: {SURFACE_ALT};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 9px 8px;
    font-size: 8.5pt;
    font-weight: 700;
}}
QTableCornerButton::section {{
    background: {SURFACE_ALT};
    border: none;
}}

/* ---------------- Desplazamiento ---------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #D3CEC3;
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #B9B3A7;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #D3CEC3;
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QStackedWidget {{
    background: transparent;
}}

/* ---------------- Menús y diálogos ---------------- */
QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {PRIMARY_SOFT};
    color: {TEXT};
}}
QMessageBox {{
    background: {SURFACE};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QDialog QLabel#DialogTitle {{
    font-size: 17pt;
    font-weight: 700;
}}
QDialog QLabel#DialogSubtitle {{
    color: {MUTED};
    font-size: 9pt;
}}
"""
