from __future__ import annotations

from pos import config
from pos.repositories import inventory as inventory_repo
from pos.repositories import products as products_repo
from pos.services.errors import NotFoundError, ValidationError


class InventoryService:
    def __init__(self, db) -> None:
        self.db = db

    def list_movements(
        self, *, limit: int = 100, product_id: int | None = None, search: str = ""
    ) -> list[dict]:
        with self.db.read() as conn:
            return inventory_repo.list_movements(
                conn, limit=limit, product_id=product_id, search=search
            )

    def adjust(
        self,
        product_id: int,
        *,
        mode: str,
        quantity,
        note: str = "",
        reference: str = "",
    ) -> dict:
        if mode not in {"entrada", "merma", "ajuste"}:
            raise ValidationError("El tipo de movimiento no es válido.")
        try:
            target = config.parse_quantity(quantity, allow_zero=(mode == "ajuste"))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        note = " ".join(note.strip().split()) if note else ""
        if mode in {"merma", "ajuste"} and len(note) < 3:
            raise ValidationError("Indica el motivo del movimiento (mínimo 3 caracteres).")
        if not note:
            note = "Entrada de mercancía"
        if len(note) > 200:
            raise ValidationError("El motivo no puede superar los 200 caracteres.")

        now = config.utc_now_iso()
        with self.db.transaction() as conn:
            product = products_repo.get_product(conn, product_id)
            if product is None:
                raise NotFoundError("El producto ya no existe.")

            previous = round(float(product["stock"]), 3)
            if mode == "entrada":
                new_stock = round(previous + target, 3)
                kind = "entrada"
            elif mode == "merma":
                new_stock = round(previous - target, 3)
                kind = "merma"
            else:
                new_stock = round(target, 3)
                kind = "ajuste"

            if new_stock < 0:
                raise ValidationError(
                    f"No hay stock suficiente. Existencias actuales: {config.quantity(previous)}."
                )
            if mode == "ajuste" and new_stock == previous:
                raise ValidationError("El stock indicado es igual al actual; no hay cambios.")
            if mode in {"entrada", "merma"} and target == 0:
                raise ValidationError("La cantidad debe ser mayor que cero.")

            delta = round(new_stock - previous, 3)
            products_repo.set_stock(conn, product_id, new_stock, now)
            inventory_repo.add_movement(
                conn,
                product_id=product_id,
                kind=kind,
                quantity_delta=delta,
                stock_after=new_stock,
                reference=reference.strip() or "Ajuste manual",
                note=note,
                created_at=now,
            )

        return {
            "product_id": product_id,
            "product_name": product["name"],
            "previous_stock": previous,
            "stock": new_stock,
            "delta": delta,
            "kind": kind,
        }
