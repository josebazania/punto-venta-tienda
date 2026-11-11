from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pos import config
from pos.db.migrations import MIGRATIONS, SCHEMA_VERSION


class DatabaseError(RuntimeError):
    """Error de infraestructura de base de datos."""


class Database:
    """Administra conexiones SQLite, migraciones y respaldos."""

    def __init__(self, path: str | Path | None = None, *, demo_data: bool = True) -> None:
        self.path = Path(path or config.DB_PATH).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()
        from pos.db.seed import seed_database

        seed_database(self, demo_data=demo_data)

    # ------------------------------------------------------------------
    # Conexiones
    # ------------------------------------------------------------------
    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 8000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self._new_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._new_connection()
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Migraciones
    # ------------------------------------------------------------------
    def _migrate(self) -> None:
        is_new = not self.path.exists() or self.path.stat().st_size == 0
        conn = sqlite3.connect(str(self.path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            row = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
            current = int(row["version"])
            if not is_new and current < SCHEMA_VERSION:
                self._backup_before_migration(current)

            for version, name, sql in MIGRATIONS:
                if version <= current:
                    continue
                applied_at = (
                    datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                # La migración 2 reconstruye sales, referenciada por otras tablas.
                if version == 2:
                    conn.execute("PRAGMA foreign_keys = OFF")
                script = (
                    "BEGIN IMMEDIATE;\n"
                    f"{sql}\n"
                    + ("CREATE TEMP TABLE migration_fk_check (ok INTEGER NOT NULL);\n"
                       "INSERT INTO migration_fk_check SELECT NULL FROM pragma_foreign_key_check LIMIT 1;\n"
                       "DROP TABLE migration_fk_check;\n" if version == 2 else "")
                    + "INSERT INTO schema_migrations(version, name, applied_at) "
                    f"VALUES ({version}, '{name}', '{applied_at}');\n"
                    "COMMIT;"
                )
                try:
                    conn.executescript(script)
                    if version == 2:
                        conn.execute("PRAGMA foreign_keys = ON")
                        if conn.execute("PRAGMA foreign_key_check").fetchone():
                            raise DatabaseError("La migración dejó referencias inválidas.")
                except sqlite3.Error:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    raise
        finally:
            conn.close()

    def _backup_before_migration(self, version: int) -> None:
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = config.BACKUP_DIR / f"pos-pre-migracion-v{version}-{stamp}.db"
        with closing(sqlite3.connect(str(self.path))) as source:
            with closing(sqlite3.connect(str(destination))) as backup:
                source.backup(backup)

    def backup(self, destination: str | Path) -> Path:
        target = Path(destination).expanduser().resolve()
        if target == self.path:
            raise ValueError("Elige una ubicación distinta a la base de datos en uso.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.read() as source:
            with closing(sqlite3.connect(str(target))) as dest:
                source.backup(dest)
                dest.commit()
        return target

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def count(self, table: str) -> int:
        allowed = {"products", "sales", "cash_sessions", "categories", "inventory_movements"}
        if table not in allowed:
            raise ValueError("Tabla no permitida.")
        with self.read() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"])

    def healthcheck(self) -> tuple[bool, str]:
        try:
            with self.read() as conn:
                conn.execute("SELECT 1").fetchone()
            return True, "Conexión correcta"
        except sqlite3.Error as exc:  # pragma: no cover - defensivo
            return False, str(exc)
