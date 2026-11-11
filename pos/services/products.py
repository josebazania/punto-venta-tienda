from __future__ import annotations

import sqlite3

from pos import config
from pos.repositories import products as products_repo
from pos.services.errors import ConflictError, NotFoundError, ValidationError


class ProductService:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def list(
        self,
        *,
        search: str = "",
        category_id: int | None = None,
        active: bool | None = True,
        in_stock_only: bool = False,
        low_stock_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        with self.db.read() as conn:
            return products_repo.list_products(
                conn,
                search=search,
                category_id=category_id,
                active=active,
                in_stock_only=in_stock_only,
                low_stock_only=low_stock_only,
                limit=limit,
            )

    def list_all(self) -> list[dict]:
        with self.db.read() as conn:
            return products_repo.list_all_products(conn)

    def get(self, product_id: int) -> dict:
        with self.db.read() as conn:
            product = products_repo.get_product(conn, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")
        return product

    def find_by_code(self, code: str) -> dict | None:
        with self.db.read() as conn:
            return products_repo.find_by_code(conn, code)

    def categories(self) -> list[dict]:
        with self.db.read() as conn:
            return products_repo.list_categories(conn)

    def low_stock(self, limit: int = 20) -> list[dict]:
        with self.db.read() as conn:
            return products_repo.list_products(
                conn, active=True, low_stock_only=True, limit=limit
            )

    # ------------------------------------------------------------------
    # Altas y edición
    # ------------------------------------------------------------------
    def create(self, data: dict) -> int:
        clean = self._validate(data, is_new=True)
        now = config.utc_now_iso()
        try:
            with self.db.transaction() as conn:
                sku = clean["sku"] or products_repo.next_sku(conn)
                if products_repo.sku_exists(conn, sku):
                    raise ConflictError(f"Ya existe un producto con el código {sku}.")
                if clean["barcode"] and products_repo.barcode_exists(conn, clean["barcode"]):
                    raise ConflictError(
                        f"El código de barras {clean['barcode']} ya está registrado."
                    )
                clean["sku"] = sku
                product_id = products_repo.create_product(conn, clean, now)
                if clean["stock"] > 0:
                    from pos.repositories import inventory as inventory_repo

                    inventory_repo.add_movement(
                        conn,
                        product_id=product_id,
                        kind="inicial",
                        quantity_delta=clean["stock"],
                        stock_after=clean["stock"],
                        reference="Alta de producto",
                        note="Stock inicial",
                        created_at=now,
                    )
                return product_id
        except sqlite3.IntegrityError as exc:
            raise ConflictError("El código o el código de barras ya están en uso.") from exc

    def update(self, product_id: int, data: dict) -> None:
        clean = self._validate(data, is_new=False, product_id=product_id)
        now = config.utc_now_iso()
        try:
            with self.db.transaction() as conn:
                existing = products_repo.get_product(conn, product_id)
                if existing is None:
                    raise NotFoundError("El producto ya no existe.")
                if products_repo.sku_exists(conn, clean["sku"], exclude_id=product_id):
                    raise ConflictError(f"Ya existe un producto con el código {clean['sku']}.")
                if clean["barcode"] and products_repo.barcode_exists(
                    conn, clean["barcode"], exclude_id=product_id
                ):
                    raise ConflictError(
                        f"El código de barras {clean['barcode']} ya está registrado."
                    )
                products_repo.update_product(conn, product_id, clean, now)
        except sqlite3.IntegrityError as exc:
            raise ConflictError("El código o el código de barras ya están en uso.") from exc

    def set_active(self, product_id: int, active: bool) -> None:
        with self.db.transaction() as conn:
            existing = products_repo.get_product(conn, product_id)
            if existing is None:
                raise NotFoundError("El producto ya no existe.")
            products_repo.set_active(conn, product_id, active, config.utc_now_iso())

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    def create_category(self, name: str) -> int:
        name = " ".join(str(name).strip().split())
        if not 2 <= len(name) <= 50:
            raise ValidationError("El nombre de la categoría debe tener entre 2 y 50 caracteres.")
        try:
            with self.db.transaction() as conn:
                if products_repo.category_name_exists(conn, name):
                    raise ConflictError(f"La categoría «{name}» ya existe.")
                return products_repo.create_category(conn, name, config.utc_now_iso())
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"La categoría «{name}» ya existe.") from exc

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def _validate(self, data: dict, *, is_new: bool, product_id: int | None = None) -> dict:
        name = " ".join(str(data.get("name", "")).strip().split())
        if not 2 <= len(name) <= 120:
            raise ValidationError("El nombre del producto debe tener entre 2 y 120 caracteres.")

        sku = str(data.get("sku") or "").strip().upper()
        if is_new and not sku:
            sku = ""
        elif not sku:
            raise ValidationError("El código interno del producto es obligatorio.")
        else:
            if not 2 <= len(sku) <= 20 or not all(
                char.isalnum() or char in "-_" for char in sku
            ):
                raise ValidationError(
                    "El código interno debe tener entre 2 y 20 letras, números, guiones o guiones bajos."
                )

        barcode_raw = str(data.get("barcode") or "").strip()
        if len(barcode_raw) > 64:
            raise ValidationError("El código de barras no puede superar los 64 caracteres.")
        barcode = barcode_raw or None

        try:
            category_id = int(data["category_id"]) if data.get("category_id") not in (None, "") else None
        except (TypeError, ValueError) as exc:
            raise ValidationError("La categoría seleccionada no es válida.") from exc

        with self.db.read() as conn:
            if category_id is not None and products_repo.get_category(conn, category_id) is None:
                raise NotFoundError("La categoría seleccionada ya no existe.")
            if product_id is not None and products_repo.get_product(conn, product_id) is None:
                raise NotFoundError("El producto ya no existe.")

        unit = str(data.get("unit") or "pieza").strip().lower()
        if unit not in config.UNITS:
            raise ValidationError("La unidad seleccionada no es válida.")

        cost_cents = self._cents(data.get("cost_cents", 0), "costo")
        price_cents = self._cents(data.get("price_cents", 0), "precio de venta")
        if price_cents <= 0:
            raise ValidationError("El precio de venta debe ser mayor que cero.")

        try:
            min_stock = config.parse_quantity(data.get("min_stock", 0), allow_zero=True)
            stock = config.parse_quantity(data.get("stock", 0), allow_zero=True) if is_new else 0.0
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        return {
            "name": name,
            "sku": sku,
            "barcode": barcode,
            "category_id": category_id,
            "unit": unit,
            "cost_cents": cost_cents,
            "price_cents": price_cents,
            "stock": stock,
            "min_stock": min_stock,
            "active": bool(data.get("active", True)),
        }

    @staticmethod
    def _cents(value, label: str) -> int:
        if isinstance(value, bool):
            raise ValidationError(f"El {label} no es válido.")
        try:
            amount = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"El {label} no es válido.") from exc
        if amount < 0:
            raise ValidationError(f"El {label} no puede ser negativo.")
        return amount
