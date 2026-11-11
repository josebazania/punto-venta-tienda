from __future__ import annotations

from typing import TYPE_CHECKING

from pos import config

if TYPE_CHECKING:
    from pos.db.database import Database

CATEGORIES = (
    "Abarrotes",
    "Bebidas",
    "Limpieza",
    "Lácteos",
    "Snacks",
    "Panadería",
    "Frutas y verduras",
)

# (sku, barcode, nombre, categoría, unidad, costo_c, precio_c, stock, stock_mínimo)
DEMO_PRODUCTS = (
    ("P0001", "7751234000019", "Arroz Costeño 1 kg", "Abarrotes", "pieza", 380, 480, 40.0, 10.0),
    ("P0002", "7751234000026", "Azúcar rubia 1 kg", "Abarrotes", "pieza", 330, 420, 30.0, 8.0),
    ("P0003", "7751234000033", "Aceite vegetal 1 L", "Abarrotes", "pieza", 820, 990, 24.0, 6.0),
    ("P0004", "7751234000040", "Fideos tallarín 500 g", "Abarrotes", "pieza", 260, 350, 35.0, 10.0),
    ("P0005", "7751234000057", "Atún en lata 170 g", "Abarrotes", "pieza", 470, 590, 18.0, 6.0),
    ("P0006", "7751234000064", "Sal Emsal 1 kg", "Abarrotes", "pieza", 130, 200, 20.0, 5.0),
    ("P0007", "7751234000071", "Inca Kola 1.5 L", "Bebidas", "pieza", 580, 750, 18.0, 6.0),
    ("P0008", "7751234000088", "Agua San Mateo 625 ml", "Bebidas", "pieza", 120, 200, 30.0, 10.0),
    ("P0009", "7751234000095", "Jugo Frugos 1 L", "Bebidas", "pieza", 350, 450, 12.0, 5.0),
    ("P0010", "7751234000101", "Detergente Bolívar 1 kg", "Limpieza", "pieza", 920, 1150, 14.0, 4.0),
    ("P0011", "7751234000118", "Papel higiénico Elite x4", "Limpieza", "paquete", 710, 890, 10.0, 4.0),
    ("P0012", "7751234000125", "Lejía Clorox 1 L", "Limpieza", "pieza", 360, 480, 9.0, 3.0),
    ("P0013", "7751234000132", "Leche evaporada 400 g", "Lácteos", "pieza", 360, 440, 28.0, 8.0),
    ("P0014", "7751234000149", "Yogurt Gloria 1 L", "Lácteos", "pieza", 500, 650, 8.0, 4.0),
    ("P0015", "7751234000156", "Queso fresco 250 g", "Lácteos", "pieza", 620, 790, 4.0, 2.0),
    ("P0016", "7751234000163", "Galletas Oreo 6 pack", "Snacks", "paquete", 500, 650, 15.0, 5.0),
    ("P0017", "7751234000170", "Papas Lays 150 g", "Snacks", "pieza", 420, 550, 3.0, 5.0),
    ("P0018", "7751234000187", "Chocolate Sublime", "Snacks", "pieza", 190, 280, 0.0, 6.0),
    ("P0019", "", "Pan francés", "Panadería", "kg", 450, 800, 12.5, 3.0),
    ("P0020", "", "Plátano de seda", "Frutas y verduras", "kg", 220, 350, 15.75, 4.0),
    ("P0021", "", "Tomate italiano", "Frutas y verduras", "kg", 280, 420, 8.25, 3.0),
)


def seed_database(db: "Database", *, demo_data: bool = True) -> None:
    """Crea ajustes, categorías y datos de demostración en una BD nueva."""
    now = config.utc_now_iso()
    with db.transaction() as conn:
        for key, value in config.DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )

        category_count = conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
        if int(category_count) == 0:
            conn.executemany(
                "INSERT INTO categories(name, created_at) VALUES (?, ?)",
                [(name, now) for name in CATEGORIES],
            )

        if not demo_data:
            return

        seeded = conn.execute(
            "SELECT value FROM settings WHERE key = 'demo_seeded'"
        ).fetchone()
        if seeded and seeded["value"] == "1":
            return

        product_count = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
        if int(product_count) > 0:
            return

        category_rows = conn.execute("SELECT id, name FROM categories").fetchall()
        category_ids = {row["name"]: int(row["id"]) for row in category_rows}
        for sku, barcode, name, category, unit, cost, price, stock, minimum in DEMO_PRODUCTS:
            cursor = conn.execute(
                """
                INSERT INTO products(
                    sku, barcode, name, category_id, unit, cost_cents, price_cents,
                    stock, min_stock, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    sku,
                    barcode or None,
                    name,
                    category_ids.get(category),
                    unit,
                    cost,
                    price,
                    stock,
                    minimum,
                    now,
                    now,
                ),
            )
            if stock > 0:
                conn.execute(
                    """
                    INSERT INTO inventory_movements(
                        product_id, kind, quantity_delta, stock_after, reference, note, created_at
                    ) VALUES (?, 'inicial', ?, ?, 'Carga demo', 'Stock inicial de demostración', ?)
                    """,
                    (int(cursor.lastrowid), stock, stock, now),
                )

        conn.execute(
            "INSERT INTO settings(key, value) VALUES ('demo_seeded', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
