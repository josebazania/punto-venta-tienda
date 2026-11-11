from __future__ import annotations

from PySide6.QtCore import QDate, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

from pos import config
from pos.ui.common import Card, KpiCard, PageHeader, label, show_error


class BarChart(QWidget):
    """Gráfico de barras horizontales con valores explícitos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumHeight(210)

    def set_rows(self, rows):
        self.rows = rows
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#63756d"))
        if not self.rows:
            painter.drawText(self.rect(), Qt.AlignCenter, "Sin datos en este periodo")
            return
        maximum = max((value for _, value, _ in self.rows), default=0) or 1
        height = max(28, min(42, self.height() // len(self.rows)))
        label_width = min(150, int(self.width() * .36))
        bar_width = max(15, self.width() - label_width - 105)
        for index, (name, value, display) in enumerate(self.rows):
            y = index * height + 5
            painter.setPen(QColor("#34483f"))
            text = painter.fontMetrics().elidedText(str(name), Qt.ElideRight, label_width - 8)
            painter.drawText(QRectF(0, y, label_width - 5, 22), Qt.AlignVCenter, text)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#e7f0eb"))
            painter.drawRoundedRect(QRectF(label_width, y + 3, bar_width, 16), 5, 5)
            painter.setBrush(QColor("#1f8a70"))
            painter.drawRoundedRect(QRectF(label_width, y + 3, max(0, bar_width * value / maximum), 16), 5, 5)
            painter.setPen(QColor("#34483f"))
            painter.drawText(QRectF(label_width + bar_width + 6, y, 95, 22), Qt.AlignVCenter, display)


class StatisticsView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        header = PageHeader("Estadísticas", "Ventas completadas, métodos de pago y productos más vendidos.")
        self.period = QComboBox()
        for name, key in (("Últimos 7 días", "7"), ("Últimos 30 días", "30"), ("Este mes", "month")):
            self.period.addItem(name, key)
        self.period.currentIndexChanged.connect(self.refresh)
        header.add_action(self.period)
        root.addWidget(header)
        kpis = QHBoxLayout()
        self.total_kpi = KpiCard("Ventas del periodo", "S/ 0.00")
        self.count_kpi = KpiCard("Ventas completadas", "0")
        self.average_kpi = KpiCard("Ticket promedio", "S/ 0.00")
        for card in (self.total_kpi, self.count_kpi, self.average_kpi):
            kpis.addWidget(card, 1)
        root.addLayout(kpis)
        charts = QHBoxLayout()
        self.payment_chart = BarChart()
        self.product_chart = BarChart()
        payment_card = Card("Métodos de pago", "Importe total por método, en soles.")
        payment_card.body().addWidget(self.payment_chart, 1)
        product_card = Card("Productos más vendidos", "Cinco productos con más unidades vendidas.")
        product_card.body().addWidget(self.product_chart, 1)
        charts.addWidget(payment_card, 1)
        charts.addWidget(product_card, 1)
        root.addLayout(charts, 1)
        daily_card = Card("Evolución de ventas", "Importe por día con ventas completadas.")
        self.daily_chart = BarChart()
        self.daily_chart.setMinimumHeight(180)
        daily_card.body().addWidget(self.daily_chart, 1)
        self.daily_note = label("", "Muted")
        daily_card.body().addWidget(self.daily_note)
        root.addWidget(daily_card, 1)
        self.refresh()

    def refresh(self):
        today = QDate.currentDate()
        key = self.period.currentData()
        start = QDate(today.year(), today.month(), 1) if key == "month" else today.addDays(-(int(key or 7) - 1))
        try:
            data = self.ctx.reports.statistics(start.toString(Qt.ISODate), today.toString(Qt.ISODate))
        except Exception as exc:
            show_error(self, exc)
            return
        self.total_kpi.set_value(config.money(data["total"]))
        self.count_kpi.set_value(str(data["count"]))
        self.average_kpi.set_value(config.money(round(data["total"] / data["count"]) if data["count"] else 0))
        self.payment_chart.set_rows([(config.PAYMENT_LABELS.get(x["method"], x["method"]), x["total"], config.money(x["total"])) for x in data["payments"]])
        self.product_chart.set_rows([(x["name"], x["quantity"], f"{config.quantity(x['quantity'])} {x['unit']}") for x in data["products"]])
        # Muestra los siete últimos días con ventas para conservar legibilidad.
        recent = data["daily"][-7:]
        self.daily_chart.set_rows([(x["day"][5:], x["total"], config.money(x["total"])) for x in recent])
        self.daily_note.setText("Se muestran los 7 días con ventas más recientes del periodo." if len(data["daily"]) > 7 else "")
