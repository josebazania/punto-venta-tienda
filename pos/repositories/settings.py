from __future__ import annotations

import sqlite3


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row is not None else default


def get_all(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def set_many(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.executemany(
        """
        INSERT INTO settings(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        [(str(key), str(value)) for key, value in values.items()],
    )
