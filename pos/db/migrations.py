from __future__ import annotations

SCHEMA_VERSION = 2

# Cada migración se aplica una sola vez y queda registrada en schema_migrations.
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "esquema_inicial",
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
            barcode TEXT COLLATE NOCASE UNIQUE,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            unit TEXT NOT NULL DEFAULT 'pieza',
            cost_cents INTEGER NOT NULL DEFAULT 0 CHECK (cost_cents >= 0),
            price_cents INTEGER NOT NULL CHECK (price_cents > 0),
            stock REAL NOT NULL DEFAULT 0 CHECK (stock >= 0),
            min_stock REAL NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_products_name ON products(name COLLATE NOCASE);
        CREATE INDEX idx_products_category ON products(category_id);
        CREATE INDEX idx_products_active ON products(active);

        CREATE TABLE cash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            opening_cash_cents INTEGER NOT NULL CHECK (opening_cash_cents >= 0),
            counted_cash_cents INTEGER,
            expected_cash_cents INTEGER,
            difference_cents INTEGER,
            status TEXT NOT NULL DEFAULT 'abierta' CHECK (status IN ('abierta', 'cerrada')),
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE UNIQUE INDEX ux_cash_sessions_open
            ON cash_sessions(status) WHERE status = 'abierta';

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT NOT NULL UNIQUE,
            cash_session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
            subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0),
            discount_cents INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
            total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
            payment_method TEXT NOT NULL CHECK (payment_method IN ('efectivo', 'tarjeta', 'transferencia')),
            cash_received_cents INTEGER NOT NULL DEFAULT 0 CHECK (cash_received_cents >= 0),
            change_cents INTEGER NOT NULL DEFAULT 0 CHECK (change_cents >= 0),
            status TEXT NOT NULL DEFAULT 'completada' CHECK (status IN ('completada', 'anulada')),
            created_at TEXT NOT NULL,
            cancelled_at TEXT,
            cancel_reason TEXT
        );
        CREATE INDEX idx_sales_created ON sales(created_at);
        CREATE INDEX idx_sales_session ON sales(cash_session_id);
        CREATE INDEX idx_sales_status ON sales(status);

        CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
            quantity REAL NOT NULL CHECK (quantity > 0),
            discount_cents INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
            line_total_cents INTEGER NOT NULL CHECK (line_total_cents >= 0)
        );
        CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);
        CREATE INDEX idx_sale_items_product ON sale_items(product_id);

        CREATE TABLE cash_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
            kind TEXT NOT NULL CHECK (kind IN ('ingreso', 'egreso', 'devolucion')),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            concept TEXT NOT NULL,
            sale_id INTEGER REFERENCES sales(id),
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_cash_movements_session ON cash_movements(cash_session_id);

        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            kind TEXT NOT NULL CHECK (kind IN ('inicial', 'venta', 'cancelacion', 'entrada', 'merma', 'ajuste')),
            quantity_delta REAL NOT NULL,
            stock_after REAL NOT NULL CHECK (stock_after >= 0),
            reference TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_inventory_movements_product ON inventory_movements(product_id);
        CREATE INDEX idx_inventory_movements_created ON inventory_movements(created_at);

        CREATE TABLE sale_counters (
            day TEXT PRIMARY KEY,
            next_number INTEGER NOT NULL
        );
        """,
    ),
    (
        2,
        "agregar_pago_yape",
        """
        CREATE TABLE sales_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT NOT NULL UNIQUE,
            cash_session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
            subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0),
            discount_cents INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
            total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
            payment_method TEXT NOT NULL CHECK (payment_method IN ('efectivo', 'tarjeta', 'transferencia', 'yape')),
            cash_received_cents INTEGER NOT NULL DEFAULT 0 CHECK (cash_received_cents >= 0),
            change_cents INTEGER NOT NULL DEFAULT 0 CHECK (change_cents >= 0),
            status TEXT NOT NULL DEFAULT 'completada' CHECK (status IN ('completada', 'anulada')),
            created_at TEXT NOT NULL,
            cancelled_at TEXT,
            cancel_reason TEXT
        );
        INSERT INTO sales_new SELECT * FROM sales;
        DROP TABLE sales;
        ALTER TABLE sales_new RENAME TO sales;
        CREATE INDEX idx_sales_created ON sales(created_at);
        CREATE INDEX idx_sales_session ON sales(cash_session_id);
        CREATE INDEX idx_sales_status ON sales(status);
        """,
    ),
]
