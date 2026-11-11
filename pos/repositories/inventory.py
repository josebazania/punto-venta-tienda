from __future__ import annotations

import sqlite3

from pos.repositories._common import like_pattern, many


def add_movement(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    kind: str,
    quantity_delta: float,
    stock_after: float,
    reference: str,
    note: str,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO inventory_movements(
            product_id, kind, quantity_delta, stock_after, reference, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(product_id),
            kind,
            round(float(quantity_delta), 3),
            round(float(stock_after), 3),
            reference,
            note,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def list_movements(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    product_id: int | None = None,
    search: str = "",
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if product_id is not None:
        clauses.append("m.product_id = ?")
        params.append(int(product_id))
    query = search.strip()
    if query:
        pattern = like_pattern(query)
        clauses.append(
            "(p.name LIKE ? ESCAPE '\\' OR p.sku LIKE ? ESCAPE '\\' "
            "OR m.reference LIKE ? ESCAPE '\\' OR m.note LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern, pattern, pattern, pattern])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 1000)))
    rows = conn.execute(
        f"""
        SELECT m.*, p.name AS product_name, p.sku AS product_sku
        FROM inventory_movements m
        JOIN products p ON p.id = m.product_id
        {where}
        ORDER BY m.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return many(rows)


def count_movements(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM inventory_movements").fetchone()
    return int(row["n"])
