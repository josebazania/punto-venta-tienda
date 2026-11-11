from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos.context import AppContext
from pos.db.migrations import MIGRATIONS

from pos.db.database import Database


class DatabaseTests(unittest.TestCase):
    def test_schema_and_defaults_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "pos.db", demo_data=False)
            with db.read() as conn:
                version = conn.execute(
                    "SELECT MAX(version) AS v FROM schema_migrations"
                ).fetchone()["v"]
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                setting = conn.execute(
                    "SELECT value FROM settings WHERE key = 'business_name'"
                ).fetchone()["value"]
            self.assertEqual(version, 2)
            self.assertIn("sales", tables)
            self.assertIn("cash_sessions", tables)
            self.assertIn("inventory_movements", tables)
            self.assertEqual(setting, "Abarrotes La Esquina")
            self.assertEqual(db.count("products"), 0)
            self.assertGreaterEqual(db.count("categories"), 7)

    def test_demo_data_is_seeded_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pos.db"
            first = Database(path, demo_data=True)
            count = first.count("products")
            self.assertEqual(count, 21)
            second = Database(path, demo_data=True)
            self.assertEqual(second.count("products"), count)

    def test_upgrade_preserves_sales_and_foreign_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            with patch("pos.db.database.MIGRATIONS", MIGRATIONS[:1]), \
                 patch("pos.db.database.SCHEMA_VERSION", 1):
                old = Database(path, demo_data=True)
            ctx = AppContext(old)
            ctx.cash.open(1000)
            product = ctx.products.list(limit=1)[0]
            sale = ctx.sales.checkout([{"product_id": product["id"], "quantity": 1}],
                                      payment_method="tarjeta")
            with patch("pos.config.BACKUP_DIR", Path(tmp) / "backups"):
                upgraded = Database(path, demo_data=False)
            new_ctx = AppContext(upgraded)
            self.assertEqual(new_ctx.sales.get(sale["id"])["items"], sale["items"])
            with upgraded.read() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(len(list((Path(tmp) / "backups").glob("*.db"))), 1)
            yape = new_ctx.sales.checkout([{"product_id": product["id"], "quantity": 1}],
                                          payment_method="yape")
            self.assertEqual(yape["payment_method"], "yape")

    def test_backup_creates_a_readable_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "pos.db", demo_data=True)
            destination = db.backup(Path(tmp) / "backups" / "copia.db")
            self.assertTrue(destination.exists())
            copy = Database(destination, demo_data=False)
            self.assertEqual(copy.count("products"), 21)
            self.assertEqual(copy.count("categories"), 7)

    def test_backup_rejects_the_active_database_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "pos.db", demo_data=False)
            with self.assertRaises(ValueError):
                db.backup(db.path)

    def test_reopen_preserves_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pos.db"
            first = Database(path, demo_data=False)
            with first.transaction() as conn:
                conn.execute(
                    "INSERT INTO categories(name, created_at) VALUES ('Prueba', '2026-01-01T00:00:00Z')"
                )
            second = Database(path, demo_data=False)
            with second.read() as conn:
                row = conn.execute(
                    "SELECT name FROM categories WHERE name = 'Prueba'"
                ).fetchone()
            self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
