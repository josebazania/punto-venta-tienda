from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from pos import config
from pos.repositories import cash as cash_repo
from pos.repositories import inventory as inventory_repo
from pos.repositories import products as products_repo
from pos.repositories import sales as sales_repo
from pos.services.errors import ConflictError, NotFoundError, ValidationError

_QTY_STEP = Decimal("0.001")


class SaleService:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def list(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
        search: str = "",
        limit: int = 300,
    ) -> list[dict]:
        with self.db.read() as conn:
            return sales_repo.list_sales(
                conn,
                date_from=date_from,
                date_to=date_to,
                status=status,
                search=search,
                limit=limit,
            )

    def get(self, sale_id: int) -> dict:
        with self.db.read() as conn:
            sale = sales_repo.get_sale(conn, sale_id)
        if sale is None:
            raise NotFoundError("La venta ya no existe.")
        return sale

    def get_by_folio(self, folio: str) -> dict:
        with self.db.read() as conn:
            sale = sales_repo.get_sale_by_folio(conn, folio)
        if sale is None:
            raise NotFoundError("No se encontró una venta con ese folio.")
        return sale

    # ------------------------------------------------------------------
    # Cobro
    # ------------------------------------------------------------------
    def checkout(
        self,
        items,
        *,
        discount_cents: int = 0,
        payment_method: str = "efectivo",
        cash_received_cents: int = 0,
    ) -> dict:
        cart = self._normalize_cart(items)
        if payment_method not in config.PAYMENT_METHODS:
            raise ValidationError("El método de pago no es válido.")
        if isinstance(discount_cents, bool):
            raise ValidationError("El descuento no es válido.")
        try:
            discount_cents = int(discount_cents)
            cash_received_cents = int(cash_received_cents)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El descuento o el efectivo recibido no son válidos.") from exc
        if discount_cents < 0:
            raise ValidationError("El descuento no puede ser negativo.")
        if cash_received_cents < 0:
            raise ValidationError("El efectivo recibido no puede ser negativo.")

        now = config.utc_now_iso()
        with self.db.transaction() as conn:
            session = cash_repo.get_open_session(conn)
            if session is None:
                raise ConflictError("La caja está cerrada. Abre la caja antes de vender.")

            lines: list[dict] = []
            subtotal = 0
            for product_id, qty in cart.items():
                product = products_repo.get_product(conn, product_id)
                if product is None:
                    raise NotFoundError("Uno de los productos del carrito ya no existe.")
                if not product["active"]:
                    raise ConflictError(
                        f"El producto «{product['name']}» está inactivo y no se puede vender."
                    )
                available = Decimal(str(product["stock"]))
                if available + Decimal("0.0001") < qty:
                    raise ConflictError(
                        f"Stock insuficiente de «{product['name']}». "
                        f"Disponible: {config.quantity(float(available))}."
                    )
                total = config.line_total_cents(int(product["price_cents"]), qty)
                lines.append(
                    {
                        "product_id": int(product_id),
                        "sku": product["sku"],
                        "product_name": product["name"],
                        "unit": product["unit"],
                        "unit_price_cents": int(product["price_cents"]),
                        "quantity": float(qty),
                        "quantity_decimal": qty,
                        "discount_cents": 0,
                        "line_total_cents": total,
                    }
                )
                subtotal += total

            if discount_cents > subtotal:
                raise ValidationError("El descuento no puede superar el subtotal.")
            total = subtotal - discount_cents
            if payment_method == "efectivo":
                if cash_received_cents < total:
                    raise ValidationError(
                        f"El efectivo recibido ({config.money(cash_received_cents)}) "
                        f"no cubre el total ({config.money(total)})."
                    )
                change = cash_received_cents - total
            else:
                cash_received_cents = 0
                change = 0

            folio = sales_repo.next_folio(conn, config.local_day())
            sale_id = sales_repo.create_sale(
                conn,
                {
                    "folio": folio,
                    "cash_session_id": int(session["id"]),
                    "subtotal_cents": subtotal,
                    "discount_cents": discount_cents,
                    "total_cents": total,
                    "payment_method": payment_method,
                    "cash_received_cents": cash_received_cents,
                    "change_cents": change,
                    "created_at": now,
                },
            )

            for line in lines:
                sales_repo.add_item(
                    conn,
                    sale_id=sale_id,
                    product_id=line["product_id"],
                    sku=line["sku"],
                    product_name=line["product_name"],
                    unit=line["unit"],
                    unit_price_cents=line["unit_price_cents"],
                    quantity=line["quantity"],
                    discount_cents=line["discount_cents"],
                    line_total_cents=line["line_total_cents"],
                )
                new_stock = products_repo.decrement_stock(
                    conn, line["product_id"], line["quantity"], now
                )
                if new_stock is None:
                    raise ConflictError(
                        f"El stock de «{line['product_name']}» cambió mientras se cobraba. "
                        "Actualiza el carrito e inténtalo de nuevo."
                    )
                inventory_repo.add_movement(
                    conn,
                    product_id=line["product_id"],
                    kind="venta",
                    quantity_delta=-line["quantity"],
                    stock_after=new_stock,
                    reference=folio,
                    note="Venta",
                    created_at=now,
                )

            sale = sales_repo.get_sale(conn, sale_id)
            if sale is None:  # pragma: no cover - defensivo
                raise NotFoundError("No se pudo recuperar la venta recién registrada.")
            return sale

    # ------------------------------------------------------------------
    # Anulación
    # ------------------------------------------------------------------
    def cancel(self, sale_id: int, reason: str) -> dict:
        reason = " ".join(str(reason or "").strip().split())
        if len(reason) < 3:
            raise ValidationError("Indica el motivo de la anulación (mínimo 3 caracteres).")
        if len(reason) > 200:
            raise ValidationError("El motivo no puede superar los 200 caracteres.")

        now = config.utc_now_iso()
        with self.db.transaction() as conn:
            sale = sales_repo.get_sale(conn, sale_id)
            if sale is None:
                raise NotFoundError("La venta ya no existe.")
            if sale["status"] == config.SALE_CANCELLED:
                raise ConflictError("Esta venta ya fue anulada.")

            open_session = cash_repo.get_open_session(conn)
            needs_refund = bool(
                sale["payment_method"] == "efectivo"
                and (open_session is None or int(open_session["id"]) != int(sale["cash_session_id"]))
            )
            if needs_refund and open_session is None:
                raise ConflictError(
                    "Abre la caja para registrar la devolución en efectivo de esta venta."
                )

            sales_repo.cancel_sale(conn, sale_id, reason, now)
            for item in sale["items"]:
                product = products_repo.get_product(conn, int(item["product_id"]))
                if product is None:
                    raise NotFoundError(
                        "No se puede anular: uno de los productos ya no existe."
                    )
                restored = round(float(product["stock"]) + float(item["quantity"]), 3)
                products_repo.set_stock(conn, int(item["product_id"]), restored, now)
                inventory_repo.add_movement(
                    conn,
                    product_id=int(item["product_id"]),
                    kind="cancelacion",
                    quantity_delta=float(item["quantity"]),
                    stock_after=restored,
                    reference=f"Anulación {sale['folio']}",
                    note=reason,
                    created_at=now,
                )

            if needs_refund and open_session is not None:
                cash_repo.add_movement(
                    conn,
                    session_id=int(open_session["id"]),
                    kind="devolucion",
                    amount_cents=int(sale["total_cents"]),
                    concept=f"Devolución venta {sale['folio']}",
                    sale_id=int(sale_id),
                    when=now,
                )

            cancelled = sales_repo.get_sale(conn, sale_id)
            if cancelled is None:  # pragma: no cover - defensivo
                raise NotFoundError("No se pudo recuperar la venta anulada.")
            return cancelled

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_cart(items) -> dict[int, Decimal]:
        if not items:
            raise ValidationError("Agrega al menos un producto al carrito.")
        merged: dict[int, Decimal] = {}
        for raw in items:
            if not isinstance(raw, dict):
                raise ValidationError("El carrito contiene un producto no válido.")
            try:
                product_id = int(raw.get("product_id"))
            except (TypeError, ValueError) as exc:
                raise ValidationError("El carrito contiene un producto no válido.") from exc
            try:
                qty = Decimal(str(raw.get("quantity", "")).replace(",", "."))
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError("La cantidad de un producto no es válida.") from exc
            if qty <= 0:
                raise ValidationError("Las cantidades deben ser mayores que cero.")
            if qty != qty.quantize(_QTY_STEP, rounding=ROUND_HALF_UP):
                raise ValidationError("Las cantidades admiten como máximo 3 decimales.")
            if qty > Decimal("9999.999"):
                raise ValidationError("La cantidad de un producto es demasiado grande.")
            merged[product_id] = merged.get(product_id, Decimal("0")) + qty
        return merged
