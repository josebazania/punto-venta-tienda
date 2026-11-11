from __future__ import annotations

import sqlite3


def today_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*) AS sales_count,
               COALESCE(SUM(total_cents), 0) AS total_cents,
               COALESCE(ROUND(AVG(total_cents)), 0) AS average_cents,
               COALESCE(SUM(CASE WHEN payment_method = 'efectivo' THEN total_cents ELSE 0 END), 0) AS cash_cents,
               COALESCE(SUM(CASE WHEN payment_method = 'tarjeta' THEN total_cents ELSE 0 END), 0) AS card_cents,
               COALESCE(SUM(CASE WHEN payment_method = 'transferencia' THEN total_cents ELSE 0 END), 0) AS transfer_cents,
               COALESCE(SUM(CASE WHEN payment_method = 'yape' THEN total_cents ELSE 0 END), 0) AS yape_cents
        FROM sales
        WHERE status = 'completada'
          AND date(datetime(created_at, 'localtime')) = date('now', 'localtime')
        """
    ).fetchone()
    return {
        "sales_count": int(row["sales_count"]),
        "total_cents": int(row["total_cents"]),
        "average_cents": int(row["average_cents"]),
        "cash_cents": int(row["cash_cents"]),
        "card_cents": int(row["card_cents"]),
        "transfer_cents": int(row["transfer_cents"]),
        "yape_cents": int(row["yape_cents"]),
    }


def inventory_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total_products,
               COALESCE(SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END), 0) AS active_products,
               COALESCE(ROUND(SUM(CASE WHEN active = 1 THEN stock * cost_cents ELSE 0 END)), 0) AS stock_value_cents,
               COALESCE(SUM(CASE WHEN active = 1 AND stock <= min_stock THEN 1 ELSE 0 END), 0) AS low_stock,
               COALESCE(SUM(CASE WHEN active = 1 AND stock <= 0 THEN 1 ELSE 0 END), 0) AS out_of_stock
        FROM products
        """
    ).fetchone()
    return {
        "total_products": int(row["total_products"]),
        "active_products": int(row["active_products"]),
        "stock_value_cents": int(row["stock_value_cents"]),
        "low_stock": int(row["low_stock"]),
        "out_of_stock": int(row["out_of_stock"]),
    }


def sales_by_day(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    rows = conn.execute(
        """
        SELECT date(datetime(created_at, 'localtime')) AS day,
               COUNT(*) AS sales_count,
               COALESCE(SUM(total_cents), 0) AS total_cents
        FROM sales
        WHERE status = 'completada'
          AND date(datetime(created_at, 'localtime')) >= date('now', 'localtime', ?)
        GROUP BY day
        ORDER BY day
        """,
        (f"-{max(1, int(days)) - 1} days",),
    ).fetchall()
    return [dict(row) for row in rows]
