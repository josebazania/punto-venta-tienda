from __future__ import annotations

import sqlite3

from pos.repositories._common import like_pattern, many, one

_PRODUCT_SELECT = """
    SELECT p.*, c.name AS category_name
    FROM products p
    LEFT JOIN categories c ON c.id = p.category_id
"""


def list_products(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    category_id: int | None = None,
    active: bool | None = True,
    in_stock_only: bool = False,
    low_stock_only: bool = False,
    limit: int = 500,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    query = search.strip()
    if query:
        pattern = like_pattern(query)
        clauses.append(
            "(p.name LIKE ? ESCAPE '\\' OR p.sku LIKE ? ESCAPE '\\' "
            "OR COALESCE(p.barcode, '') LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern, pattern, pattern])
    if category_id is not None:
        clauses.append("p.category_id = ?")
        params.append(int(category_id))
    if active is not None:
        clauses.append("p.active = ?")
        params.append(1 if active else 0)
    if in_stock_only:
        clauses.append("p.stock > 0")
    if low_stock_only:
        clauses.append("p.stock <= p.min_stock")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 2000)))
    rows = conn.execute(
        f"{_PRODUCT_SELECT} {where} ORDER BY p.name COLLATE NOCASE LIMIT ?",
        params,
    ).fetchall()
    return many(rows)


def list_all_products(conn: sqlite3.Connection) -> list[dict]:
    """Lista el catálogo completo, incluidos productos inactivos."""
    return many(conn.execute(f"{_PRODUCT_SELECT} ORDER BY p.name COLLATE NOCASE, p.id").fetchall())


def get_product(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute(f"{_PRODUCT_SELECT} WHERE p.id = ?", (int(product_id),)).fetchone()
    return one(row)


def find_by_code(conn: sqlite3.Connection, code: str) -> dict | None:
    code = code.strip()
    if not code:
        return None
    row = conn.execute(
        f"{_PRODUCT_SELECT} WHERE p.active = 1 AND (p.sku = ? COLLATE NOCASE OR p.barcode = ?)",
        (code, code),
    ).fetchone()
    return one(row)


def sku_exists(conn: sqlite3.Connection, sku: str, exclude_id: int | None = None) -> bool:
    sql = "SELECT 1 FROM products WHERE sku = ? COLLATE NOCASE"
    params: list[object] = [sku]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(int(exclude_id))
    return conn.execute(sql, params).fetchone() is not None


def barcode_exists(conn: sqlite3.Connection, barcode: str, exclude_id: int | None = None) -> bool:
    sql = "SELECT 1 FROM products WHERE barcode = ? COLLATE NOCASE"
    params: list[object] = [barcode]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(int(exclude_id))
    return conn.execute(sql, params).fetchone() is not None


def next_sku(conn: sqlite3.Connection) -> str:
    used = {
        str(row["sku"]).upper()
        for row in conn.execute("SELECT sku FROM products").fetchall()
    }
    number = 1
    while f"P{number:04d}" in used:
        number += 1
    return f"P{number:04d}"


def create_product(conn: sqlite3.Connection, data: dict, now: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO products(
            sku, barcode, name, category_id, unit, cost_cents, price_cents,
            stock, min_stock, active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["sku"],
            data["barcode"],
            data["name"],
            data["category_id"],
            data["unit"],
            data["cost_cents"],
            data["price_cents"],
            data["stock"],
            data["min_stock"],
            1 if data["active"] else 0,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def update_product(conn: sqlite3.Connection, product_id: int, data: dict, now: str) -> None:
    conn.execute(
        """
        UPDATE products SET
            sku = ?, barcode = ?, name = ?, category_id = ?, unit = ?,
            cost_cents = ?, price_cents = ?, min_stock = ?, active = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            data["sku"],
            data["barcode"],
            data["name"],
            data["category_id"],
            data["unit"],
            data["cost_cents"],
            data["price_cents"],
            data["min_stock"],
            1 if data["active"] else 0,
            now,
            int(product_id),
        ),
    )


def set_active(conn: sqlite3.Connection, product_id: int, active: bool, now: str) -> None:
    conn.execute(
        "UPDATE products SET active = ?, updated_at = ? WHERE id = ?",
        (1 if active else 0, now, int(product_id)),
    )


def set_stock(conn: sqlite3.Connection, product_id: int, stock: float, now: str) -> None:
    conn.execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (round(float(stock), 3), now, int(product_id)),
    )


def decrement_stock(
    conn: sqlite3.Connection, product_id: int, qty: float, now: str
) -> float | None:
    cursor = conn.execute(
        """
        UPDATE products
        SET stock = ROUND(stock - ?, 3), updated_at = ?
        WHERE id = ? AND active = 1 AND stock >= ?
        """,
        (float(qty), now, int(product_id), float(qty)),
    )
    if cursor.rowcount != 1:
        return None
    row = conn.execute("SELECT stock FROM products WHERE id = ?", (int(product_id),)).fetchone()
    return round(float(row["stock"]), 3)


# ----------------------------------------------------------------------
# Categorías
# ----------------------------------------------------------------------
def list_categories(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.id, c.name, c.created_at,
               COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE
        """
    ).fetchall()
    return many(rows)


def get_category(conn: sqlite3.Connection, category_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM categories WHERE id = ?", (int(category_id),)
    ).fetchone()
    return one(row)


def category_name_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    return row is not None


def create_category(conn: sqlite3.Connection, name: str, now: str) -> int:
    cursor = conn.execute(
        "INSERT INTO categories(name, created_at) VALUES (?, ?)", (name, now)
    )
    return int(cursor.lastrowid)
