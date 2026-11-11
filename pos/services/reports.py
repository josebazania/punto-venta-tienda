from __future__ import annotations

from pos.repositories import cash as cash_repo
from pos.repositories import products as products_repo
from pos.repositories import reports as reports_repo
from pos.repositories import sales as sales_repo


class ReportService:
    def __init__(self, db) -> None:
        self.db = db

    def dashboard(self) -> dict:
        with self.db.read() as conn:
            today = reports_repo.today_summary(conn)
            inventory = reports_repo.inventory_stats(conn)
            low_stock = products_repo.list_products(
                conn, active=True, low_stock_only=True, limit=8
            )
            recent = sales_repo.recent_sales(conn, limit=6)
            session = cash_repo.get_open_session(conn)
            cash_summary = (
                cash_repo.summarize_session(conn, int(session["id"])) if session else None
            )
        return {
            "today": today,
            "inventory": inventory,
            "low_stock": low_stock,
            "recent_sales": recent,
            "cash": cash_summary,
        }

    def inventory_overview(self) -> dict:
        with self.db.read() as conn:
            stats = reports_repo.inventory_stats(conn)
            low_stock = products_repo.list_products(
                conn, active=True, low_stock_only=True, limit=50
            )
        return {"stats": stats, "low_stock": low_stock}

    def today(self) -> dict:
        with self.db.read() as conn:
            return reports_repo.today_summary(conn)

    def sales_last_days(self, days: int = 7) -> list[dict]:
        with self.db.read() as conn:
            return reports_repo.sales_by_day(conn, days=days)

    def statistics(self, start: str, end: str) -> dict:
        """Ventas completadas por fecha, pago y producto en fechas locales inclusivas."""
        with self.db.read() as conn:
            condition = "s.status = 'completada' AND date(datetime(s.created_at, 'localtime')) BETWEEN ? AND ?"
            params = (start, end)
            daily = conn.execute(
                f"SELECT date(datetime(s.created_at, 'localtime')) AS day, SUM(s.total_cents) AS total FROM sales s WHERE {condition} GROUP BY day ORDER BY day", params
            ).fetchall()
            payments = conn.execute(
                f"SELECT s.payment_method AS method, SUM(s.total_cents) AS total FROM sales s WHERE {condition} GROUP BY s.payment_method ORDER BY total DESC", params
            ).fetchall()
            products = conn.execute(
                f"SELECT si.product_name AS name, si.unit AS unit, SUM(si.quantity) AS quantity FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE {condition} GROUP BY si.product_id, si.product_name, si.unit ORDER BY quantity DESC, si.product_name LIMIT 5", params
            ).fetchall()
            totals = conn.execute(
                f"SELECT COUNT(*) AS count, COALESCE(SUM(s.total_cents), 0) AS total FROM sales s WHERE {condition}", params
            ).fetchone()
        return {"daily": [dict(r) for r in daily], "payments": [dict(r) for r in payments],
                "products": [dict(r) for r in products], "count": int(totals["count"]),
                "total": int(totals["total"])}
