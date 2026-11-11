from __future__ import annotations

import sqlite3

from pos.repositories._common import many, one


def get_session(conn: sqlite3.Connection, session_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM cash_sessions WHERE id = ?", (int(session_id),)).fetchone()
    return one(row)


def get_open_session(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM cash_sessions WHERE status = 'abierta' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return one(row)


def open_session(conn: sqlite3.Connection, opening_cash_cents: int, notes: str, when: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO cash_sessions(opened_at, opening_cash_cents, status, notes)
        VALUES (?, ?, 'abierta', ?)
        """,
        (when, int(opening_cash_cents), notes),
    )
    return int(cursor.lastrowid)


def close_session(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    counted_cash_cents: int,
    expected_cash_cents: int,
    difference_cents: int,
    notes: str,
    when: str,
) -> None:
    conn.execute(
        """
        UPDATE cash_sessions SET
            closed_at = ?, counted_cash_cents = ?, expected_cash_cents = ?,
            difference_cents = ?, status = 'cerrada', notes = ?
        WHERE id = ? AND status = 'abierta'
        """,
        (
            when,
            int(counted_cash_cents),
            int(expected_cash_cents),
            int(difference_cents),
            notes,
            int(session_id),
        ),
    )


def add_movement(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    kind: str,
    amount_cents: int,
    concept: str,
    sale_id: int | None,
    when: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO cash_movements(cash_session_id, kind, amount_cents, concept, sale_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (int(session_id), kind, int(amount_cents), concept, sale_id, when),
    )
    return int(cursor.lastrowid)


def list_movements(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.*, s.folio AS sale_folio
        FROM cash_movements m
        LEFT JOIN sales s ON s.id = m.sale_id
        WHERE m.cash_session_id = ?
        ORDER BY m.id DESC
        """,
        (int(session_id),),
    ).fetchall()
    return many(rows)


def _payment_totals(conn: sqlite3.Connection, session_id: int) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        """
        SELECT payment_method, COUNT(*) AS count, COALESCE(SUM(total_cents), 0) AS total
        FROM sales
        WHERE cash_session_id = ? AND status = 'completada'
        GROUP BY payment_method
        """,
        (int(session_id),),
    ).fetchall()
    return {
        str(row["payment_method"]): (int(row["count"]), int(row["total"]))
        for row in rows
    }


def summarize_session(conn: sqlite3.Connection, session_id: int) -> dict | None:
    session = get_session(conn, session_id)
    if session is None:
        return None
    payments = _payment_totals(conn, session_id)
    cash_count, cash_sales = payments.get("efectivo", (0, 0))
    card_sales = payments.get("tarjeta", (0, 0))[1]
    transfer_sales = payments.get("transferencia", (0, 0))[1]
    yape_sales = payments.get("yape", (0, 0))[1]
    sales_count = sum(count for count, _ in payments.values())
    total_sales = sum(total for _, total in payments.values())

    movement_rows = conn.execute(
        """
        SELECT kind, COALESCE(SUM(amount_cents), 0) AS total
        FROM cash_movements
        WHERE cash_session_id = ?
        GROUP BY kind
        """,
        (int(session_id),),
    ).fetchall()
    movement_totals = {str(row["kind"]): int(row["total"]) for row in movement_rows}
    income = movement_totals.get("ingreso", 0)
    expenses = movement_totals.get("egreso", 0)
    refunds = movement_totals.get("devolucion", 0)

    calculated_expected = (
        int(session["opening_cash_cents"]) + cash_sales + income - expenses - refunds
    )
    stored_expected = session["expected_cash_cents"]
    expected = int(stored_expected) if stored_expected is not None else calculated_expected
    counted = session["counted_cash_cents"]
    difference = session["difference_cents"]

    return {
        **session,
        "cash_sales_cents": cash_sales,
        "cash_sales_count": cash_count,
        "card_sales_cents": card_sales,
        "transfer_sales_cents": transfer_sales,
        "yape_sales_cents": yape_sales,
        "total_sales_cents": total_sales,
        "sales_count": sales_count,
        "income_cents": income,
        "expense_cents": expenses,
        "refund_cents": refunds,
        "expected_cash_cents": expected,
        "counted_cash_cents": counted,
        "difference_cents": difference,
    }


def list_sessions(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        """
        SELECT cs.*,
               (SELECT COUNT(*) FROM sales s
                 WHERE s.cash_session_id = cs.id AND s.status = 'completada') AS sales_count,
               (SELECT COALESCE(SUM(s.total_cents), 0) FROM sales s
                 WHERE s.cash_session_id = cs.id AND s.status = 'completada') AS sales_total_cents
        FROM cash_sessions cs
        ORDER BY cs.id DESC
        LIMIT ?
        """,
        (max(1, min(int(limit), 200)),),
    ).fetchall()
    return many(rows)
