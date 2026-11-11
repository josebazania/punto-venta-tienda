from __future__ import annotations

import sqlite3

from pos.repositories._common import like_pattern, many, one

_SALE_SELECT = """
    SELECT s.*,
           (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id = s.id) AS item_count,
           (SELECT COALESCE(SUM(si.quantity), 0) FROM sale_items si WHERE si.sale_id = s.id) AS item_units
    FROM sales s
"""


def next_folio(conn: sqlite3.Connection, day: str) -> str:
    row = conn.execute(
        """
        INSERT INTO sale_counters(day, next_number) VALUES (?, 1)
        ON CONFLICT(day) DO UPDATE SET next_number = next_number + 1
        RETURNING next_number
        """,
        (day,),
    ).fetchone()
    number = int(row["next_number"])
    return f"V-{day}-{number:04d}"


def create_sale(conn: sqlite3.Connection, data: dict) -> int:
    cursor = conn.execute(
        """
        INSERT INTO sales(
            folio, cash_session_id, subtotal_cents, discount_cents, total_cents,
            payment_method, cash_received_cents, change_cents, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completada', ?)
        """,
        (
            data["folio"],
            int(data["cash_session_id"]),
            int(data["subtotal_cents"]),
            int(data["discount_cents"]),
            int(data["total_cents"]),
            data["payment_method"],
            int(data["cash_received_cents"]),
            int(data["change_cents"]),
            data["created_at"],
        ),
    )
    return int(cursor.lastrowid)


def add_item(
    conn: sqlite3.Connection,
    *,
    sale_id: int,
    product_id: int,
    sku: str,
    product_name: str,
    unit: str,
    unit_price_cents: int,
    quantity: float,
    discount_cents: int,
    line_total_cents: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO sale_items(
            sale_id, product_id, sku, product_name, unit, unit_price_cents,
            quantity, discount_cents, line_total_cents
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(sale_id),
            int(product_id),
            sku,
            product_name,
            unit,
            int(unit_price_cents),
            float(quantity),
            int(discount_cents),
            int(line_total_cents),
        ),
    )
    return int(cursor.lastrowid)


def get_sale(conn: sqlite3.Connection, sale_id: int) -> dict | None:
    row = conn.execute(f"{_SALE_SELECT} WHERE s.id = ?", (int(sale_id),)).fetchone()
    sale = one(row)
    if sale is None:
        return None
    sale["items"] = many(
        conn.execute(
            """
            SELECT si.*, p.category_id
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            ORDER BY si.id
            """,
            (int(sale_id),),
        ).fetchall()
    )
    return sale


def get_sale_by_folio(conn: sqlite3.Connection, folio: str) -> dict | None:
    row = conn.execute(f"{_SALE_SELECT} WHERE s.folio = ?", (folio.strip(),)).fetchone()
    sale = one(row)
    if sale is None:
        return None
    sale["items"] = many(
        conn.execute(
            """
            SELECT si.*, p.category_id
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            ORDER BY si.id
            """,
            (int(sale["id"]),),
        ).fetchall()
    )
    return sale


def list_sales(
    conn: sqlite3.Connection,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    search: str = "",
    limit: int = 300,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if date_from:
        clauses.append("date(datetime(s.created_at, 'localtime')) >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date(datetime(s.created_at, 'localtime')) <= ?")
        params.append(date_to)
    if status in {"completada", "anulada"}:
        clauses.append("s.status = ?")
        params.append(status)
    query = search.strip()
    if query:
        pattern = like_pattern(query)
        clauses.append(
            "(s.folio LIKE ? ESCAPE '\\' OR EXISTS ("
            "SELECT 1 FROM sale_items si WHERE si.sale_id = s.id "
            "AND (si.product_name LIKE ? ESCAPE '\\' OR si.sku LIKE ? ESCAPE '\\')))"
        )
        params.extend([pattern, pattern, pattern])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 1000)))
    rows = conn.execute(
        f"""
        {_SALE_SELECT}
        {where}
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return many(rows)


def cancel_sale(conn: sqlite3.Connection, sale_id: int, reason: str, when: str) -> None:
    conn.execute(
        """
        UPDATE sales
        SET status = 'anulada', cancelled_at = ?, cancel_reason = ?
        WHERE id = ?
        """,
        (when, reason, int(sale_id)),
    )


def recent_sales(conn: sqlite3.Connection, limit: int = 6) -> list[dict]:
    return list_sales(conn, limit=limit)
