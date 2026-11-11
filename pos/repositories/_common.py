from __future__ import annotations

import sqlite3
from typing import Iterable


def one(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def many(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def like_pattern(text: str) -> str:
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    return many(cursor.fetchall())
