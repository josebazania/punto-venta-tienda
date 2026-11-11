from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pos import config
from pos.context import AppContext
from pos.services.errors import POSError
from pos.ui.common import (
    Card,
    DataTable,
    PageHeader,
    button,
    confirm,
    dialog_accepted,
    divider,
    label,
    show_error,
    table_item,
)
from pos.ui.dialogs.payment_dialog import PaymentDialog
from pos.ui.dialogs.receipt_dialog import ReceiptDialog
from pos.ui.theme import WARNING


class SaleView(QWidget):
    data_changed = Signal()
    cash_requested = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.cart: dict[int, dict] = {}
        self.products: list[dict] = []
        self._session: dict | None = None
        self._build()
        self._bind_shortcuts()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = PageHeader(
            "Punto de venta",
            "Escanea o busca un producto, arma el ticket y cobra.",
        )
        refresh_button = button("Actualizar", "Ghost")
        refresh_button.clicked.connect(self.refresh_data)
        header.add_action(refresh_button)
        root.addWidget(header)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_catalog(), 1)
        content.addWidget(self._build_ticket(), 0)
        root.addLayout(content, 1)

    def _build_catalog(self) -> QWidget:
        card = Card("Catálogo", "Doble clic en un producto para agregarlo al ticket.")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Buscar por nombre, código o escanear código de barras…"
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self._search_enter)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(160)
        self.search_timer.timeout.connect(self._load_products)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        card.body().addWidget(self.search_edit)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(170)
        self.category_combo.currentIndexChanged.connect(self._load_products)
        filters.addWidget(self.category_combo, 0)
        self.stock_check = QCheckBox("Solo con stock")
        self.stock_check.setChecked(True)
        self.stock_check.stateChanged.connect(self._load_products)
        filters.addWidget(self.stock_check)
        filters.addStretch(1)
        self.count_label = label("", "Muted")
        filters.addWidget(self.count_label)
        card.body().addLayout(filters)

        self.products_table = DataTable()
        self.products_table.configure(
            ("Código", "Producto", "Precio", "Stock"),
            (100, 0, 105, 90),
        )
        self.products_table.cellDoubleClicked.connect(self._add_from_table)
        card.body().addWidget(self.products_table, 1)

        hint_row = QHBoxLayout()
        hint_row.addWidget(label("Enter agrega el resultado exacto.", "Hint"))
        hint_row.addStretch(1)
        hint_row.addWidget(label("F2 buscar  ·  F4 cobrar", "Hint"))
        card.body().addLayout(hint_row)
        return card

    def _build_ticket(self) -> QWidget:
        ticket = QFrame()
        ticket.setObjectName("Ticket")
        ticket.setMinimumWidth(410)
        ticket.setMaximumWidth(480)
        layout = QVBoxLayout(ticket)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(label("Venta actual", "SectionTitle"))
        self.items_label = label("0 artículos", "Muted")
        title_box.addWidget(self.items_label)
        head.addLayout(title_box, 1)
        clear_link = button("Vaciar", "Link")
        clear_link.clicked.connect(self.clear_cart)
        head.addWidget(clear_link)
        layout.addLayout(head)

        self.cash_warning = QLabel()
        self.cash_warning.setObjectName("WarningLabel")
        self.cash_warning.setWordWrap(True)
        self.cash_warning.setVisible(False)
        layout.addWidget(self.cash_warning)
        self.open_cash_button = button("Abrir caja ahora", "Link")
        self.open_cash_button.setVisible(False)
        self.open_cash_button.clicked.connect(self.cash_requested.emit)
        layout.addWidget(self.open_cash_button, 0, Qt.AlignLeft)

        self.feedback_label = QLabel()
        self.feedback_label.setObjectName("SuccessLabel")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setVisible(False)
        layout.addWidget(self.feedback_label)
        self.feedback_timer = QTimer(self)
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(lambda: self.feedback_label.setVisible(False))

        self.cart_table = DataTable()
        self.cart_table.configure(("Producto", "Cant.", "Importe"), (0, 88, 96))
        self.cart_table.setMinimumHeight(240)
        layout.addWidget(self.cart_table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(5)
        for text, slot in (
            ("+", self._increment),
            ("−", self._decrement),
            ("Cantidad…", self._edit_quantity),
            ("Quitar", self._remove_selected),
        ):
            action = button(text, "Small")
            action.clicked.connect(slot)
            actions.addWidget(action)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addWidget(divider())
        subtotal_row = QHBoxLayout()
        subtotal_row.addWidget(label("Subtotal", "Muted"))
        subtotal_row.addStretch(1)
        self.subtotal_label = label(config.money(0), "FieldLabel")
        subtotal_row.addWidget(self.subtotal_label)
        layout.addLayout(subtotal_row)

        total_row = QHBoxLayout()
        total_row.addWidget(label("Total", "SectionTitle"))
        total_row.addStretch(1)
        self.total_label = label(config.money(0), "TotalValue")
        total_row.addWidget(self.total_label)
        layout.addLayout(total_row)
        layout.addWidget(
            label("El descuento se define en la ventana de cobro.", "Hint")
        )

        self.checkout_button = button("Cobrar  S/ 0.00  (F4)", "Checkout")
        self.checkout_button.clicked.connect(self.checkout)
        layout.addWidget(self.checkout_button)
        return ticket

    def _bind_shortcuts(self) -> None:
        self.focus_shortcut = QShortcut(QKeySequence("F2"), self)
        self.focus_shortcut.activated.connect(self._focus_search)
        self.checkout_shortcut = QShortcut(QKeySequence("F4"), self)
        self.checkout_shortcut.activated.connect(self.checkout)
        self.clear_shortcut = QShortcut(QKeySequence("F8"), self)
        self.clear_shortcut.activated.connect(self.clear_cart)
        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.cart_table)
        self.delete_shortcut.activated.connect(self._remove_selected)

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def refresh_data(self) -> None:
        try:
            selected_category = self.category_combo.currentData()
            categories = self.ctx.products.categories()
            self.category_combo.blockSignals(True)
            self.category_combo.clear()
            self.category_combo.addItem("Todas las categorías", None)
            for category in categories:
                self.category_combo.addItem(category["name"], int(category["id"]))
            if selected_category is not None:
                index = self.category_combo.findData(int(selected_category))
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
            self.category_combo.blockSignals(False)

            self._session = self.ctx.cash.current()
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self._load_products()
        self._sync_cart_products()
        self._update_session_state()
        self._render_cart()

    def refresh(self) -> None:
        self.refresh_data()

    def _sync_cart_products(self) -> None:
        """Actualiza precios y stock del carrito tras cambios en el catálogo."""
        if not self.cart:
            return
        messages: list[str] = []
        for product_id in list(self.cart):
            try:
                product = self.ctx.products.get(product_id)
            except POSError:
                product = None
            except Exception:
                product = None
            if product is None or not product["active"] or float(product["stock"]) <= 0:
                self.cart.pop(product_id, None)
                messages.append("Se retiró un producto que ya no está disponible.")
                continue
            entry = self.cart[product_id]
            entry["product"] = product
            stock = float(product["stock"])
            if float(entry["quantity"]) > stock:
                entry["quantity"] = round(stock, 3)
                messages.append(
                    f"La cantidad de «{product['name']}» se ajustó al stock disponible."
                )
        if messages:
            self._feedback(" ".join(dict.fromkeys(messages)), error=True)

    def _load_products(self) -> None:
        search = self.search_edit.text()
        category_id = self.category_combo.currentData()
        try:
            self.products = self.ctx.products.list(
                search=search,
                category_id=category_id,
                active=True,
                in_stock_only=self.stock_check.isChecked(),
                limit=300,
            )
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self.products_table.clear_rows()
        for product in self.products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            self.products_table.setItem(
                row,
                0,
                table_item(
                    product["sku"],
                    data=int(product["id"]),
                    tooltip=product.get("barcode") or product["sku"],
                ),
            )
            self.products_table.setItem(
                row,
                1,
                table_item(
                    product["name"],
                    data=int(product["id"]),
                    tooltip=product["name"],
                ),
            )
            self.products_table.setItem(
                row,
                2,
                table_item(
                    config.money(product["price_cents"]),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.products_table.setItem(
                row,
                3,
                table_item(
                    f"{config.quantity(product['stock'])} {product['unit']}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    color=WARNING
                    if float(product["stock"]) <= float(product["min_stock"])
                    else None,
                ),
            )
        if not self.products:
            self.products_table.show_empty(
                "No se encontraron productos con esos filtros."
            )
        self.count_label.setText(f"{len(self.products)} productos")

    def _update_session_state(self) -> None:
        closed = self._session is None
        self.cash_warning.setVisible(closed)
        self.open_cash_button.setVisible(closed)
        if closed:
            self.cash_warning.setText(
                "La caja está cerrada. Abre la caja para poder cobrar esta venta."
            )
        self.checkout_button.setEnabled(bool(self.cart) and not closed)

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    def _add_product(self, product: dict, qty: float = 1.0) -> None:
        if not product["active"]:
            self._feedback("Ese producto está inactivo.", error=True)
            return
        stock = float(product["stock"])
        if stock <= 0:
            self._feedback(
                f"«{product['name']}» no tiene stock disponible.", error=True
            )
            return
        product_id = int(product["id"])
        existing = self.cart.get(product_id)
        current_qty = float(existing["quantity"]) if existing else 0.0
        new_qty = round(current_qty + qty, 3)
        if new_qty > stock:
            self._feedback(
                f"Stock insuficiente de «{product['name']}». "
                f"Disponible: {config.quantity(stock)} {product['unit']}.",
                error=True,
            )
            return
        self.cart[product_id] = {"product": product, "quantity": new_qty}
        self._render_cart(select_id=product_id)
        self._feedback(
            f"«{product['name']}» agregado al ticket."
            if not existing
            else f"Cantidad actualizada: {config.quantity(new_qty)}."
        )

    def _render_cart(self, select_id: int | None = None) -> None:
        self.cart_table.clear_rows()
        subtotal = 0
        selected_row = -1
        for row, (product_id, entry) in enumerate(self.cart.items()):
            product = entry["product"]
            qty = float(entry["quantity"])
            amount = config.line_total_cents(int(product["price_cents"]), qty)
            subtotal += amount
            self.cart_table.insertRow(row)
            self.cart_table.setItem(
                row,
                0,
                table_item(
                    product["name"],
                    data=int(product_id),
                    tooltip=(
                        f"{config.money(product['price_cents'])} por "
                        f"{product['unit']}"
                    ),
                ),
            )
            self.cart_table.setItem(
                row,
                1,
                table_item(
                    f"{config.quantity(qty)} {product['unit']}",
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ),
            )
            self.cart_table.setItem(
                row,
                2,
                table_item(
                    config.money(amount),
                    align=Qt.AlignRight | Qt.AlignVCenter,
                    bold=True,
                ),
            )
            self.cart_table.setRowHeight(row, 40)
            if select_id is not None and product_id == select_id:
                selected_row = row
        if not self.cart:
            self.cart_table.show_empty("El carrito está vacío. Agrega un producto.")
        self.subtotal_label.setText(config.money(subtotal))
        self.total_label.setText(config.money(subtotal))
        total_items = sum(1 for _ in self.cart)
        self.items_label.setText(
            f"{total_items} artículo{'s' if total_items != 1 else ''}"
        )
        self.checkout_button.setText(f"Cobrar  {config.money(subtotal)}  (F4)")
        self._update_session_state()
        if selected_row >= 0:
            self.cart_table.selectRow(selected_row)

    def _selected_cart_id(self) -> int | None:
        row = self.cart_table.currentRow()
        if row < 0:
            return None
        item = self.cart_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return None
        return int(item.data(Qt.UserRole))

    def _increment(self) -> None:
        product_id = self._selected_cart_id()
        if product_id is None:
            self._feedback("Selecciona un producto del ticket.", error=True)
            return
        entry = self.cart[product_id]
        self._add_product(entry["product"], 1.0)

    def _decrement(self) -> None:
        product_id = self._selected_cart_id()
        if product_id is None:
            self._feedback("Selecciona un producto del ticket.", error=True)
            return
        entry = self.cart[product_id]
        new_qty = round(float(entry["quantity"]) - 1.0, 3)
        if new_qty <= 0:
            del self.cart[product_id]
        else:
            entry["quantity"] = new_qty
        self._render_cart(select_id=product_id if new_qty > 0 else None)

    def _edit_quantity(self) -> None:
        product_id = self._selected_cart_id()
        if product_id is None:
            self._feedback("Selecciona un producto del ticket.", error=True)
            return
        entry = self.cart[product_id]
        stock = float(entry["product"]["stock"])
        qty, ok = QInputDialog.getDouble(
            self,
            "Cambiar cantidad",
            f"Cantidad de «{entry['product']['name']}» ({entry['product']['unit']}):",
            float(entry["quantity"]),
            0.001,
            max(0.001, stock),
            3,
        )
        if not ok:
            return
        entry["quantity"] = round(qty, 3)
        self._render_cart(select_id=product_id)

    def _remove_selected(self) -> None:
        product_id = self._selected_cart_id()
        if product_id is None:
            return
        self.cart.pop(product_id, None)
        self._render_cart()
        self._feedback("Producto retirado del ticket.")

    def clear_cart(self) -> None:
        if not self.cart:
            return
        if not confirm(self, "Vaciar ticket", "¿Deseas quitar todos los productos del ticket?"):
            return
        self.cart.clear()
        self._render_cart()
        self._feedback("Ticket vaciado.")

    # ------------------------------------------------------------------
    # Búsqueda y cobro
    # ------------------------------------------------------------------
    def _search_enter(self) -> None:
        code = self.search_edit.text().strip()
        if not code:
            return
        try:
            product = self.ctx.products.find_by_code(code)
        except Exception as exc:
            show_error(self, exc)
            return
        if product is not None:
            self._add_product(product)
            self.search_edit.clear()
            self._focus_search()
            return
        if len(self.products) == 1:
            self._add_product(self.products[0])
            self.search_edit.clear()
            self._focus_search()

    def _add_from_table(self, row: int, column: int) -> None:
        item = self.products_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return
        try:
            product = self.ctx.products.get(int(item.data(Qt.UserRole)))
        except Exception as exc:
            show_error(self, exc)
            return
        self._add_product(product)
        self._focus_search()

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def checkout(self) -> None:
        if not self.cart:
            self._feedback("Agrega al menos un producto para cobrar.", error=True)
            return
        if self._session is None:
            self._feedback("Abre la caja antes de cobrar.", error=True)
            return
        subtotal = sum(
            config.line_total_cents(
                int(entry["product"]["price_cents"]), float(entry["quantity"])
            )
            for entry in self.cart.values()
        )
        dialog = PaymentDialog(subtotal, self)
        if not dialog_accepted(dialog) or not dialog.result_data:
            return
        payment = dialog.result_data
        items = [
            {"product_id": product_id, "quantity": entry["quantity"]}
            for product_id, entry in self.cart.items()
        ]
        try:
            sale = self.ctx.sales.checkout(
                items,
                discount_cents=payment["discount_cents"],
                payment_method=payment["payment_method"],
                cash_received_cents=payment["cash_received_cents"],
            )
        except POSError as exc:
            show_error(self, exc)
            self.refresh_data()
            return
        except Exception as exc:  # pragma: no cover - defensivo
            show_error(self, exc)
            return
        self.cart.clear()
        self._feedback("Venta registrada correctamente.")
        self.refresh_data()
        self.data_changed.emit()
        store = self.ctx.settings.get_store_info()
        pdf_path = None
        try:
            pdf_path = self.ctx.receipts.generate(sale, store)
        except Exception:
            logging.exception("No se pudo generar el PDF de la venta %s", sale["folio"])
        ReceiptDialog(
            sale,
            store,
            self,
            pdf_path=pdf_path,
            pdf_service=self.ctx.receipts,
        ).exec()
        self._focus_search()

    def _feedback(self, message: str, error: bool = False) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setObjectName("ErrorLabel" if error else "SuccessLabel")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.setVisible(True)
        self.feedback_timer.start(4500)

    def showEvent(self, event) -> None:  # noqa: N802 - API de Qt
        super().showEvent(event)
        QTimer.singleShot(0, self._focus_search)
