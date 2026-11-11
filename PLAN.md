# Plan — Punto de venta para tienda de abarrotes

**Nombre interno:** Abarrotes POS  
**Stack:** Python 3.10+ · PySide6 · SQLite 3  
**Moneda:** Soles peruanos (S/)  
**Idioma de la interfaz:** Español

---

## 1. Objetivo

Construir una aplicación de escritorio local para operar una tienda de abarrotes: vender, controlar stock, registrar movimientos de caja y consultar el historial. Debe funcionar sin internet ni servidor y guardar todo en un único archivo SQLite.

### Usuario principal
Cajero/administrador de una tienda pequeña que necesita rapidez en el mostrador y control básico de inventario.

### Resultado esperado
Un MVP instalable y usable que permita:
1. Abrir caja con fondo inicial.
2. Buscar productos por nombre, código o código de barras y cobrar en efectivo, tarjeta o transferencia.
3. Emitir/visualizar un comprobante interno e imprimirlo.
4. Controlar stock y registrar entradas, mermas y ajustes.
5. Revisar ventas, anular ventas y restaurar stock.
6. Cerrar caja con arqueo y diferencia.
7. Ver indicadores del día y productos con stock bajo.

---

## 2. Alcance funcional

### 2.1 Punto de venta
- Búsqueda incremental por nombre, SKU o código de barras.
- Filtro por categoría y filtro de disponibles.
- Agregar productos con doble clic o Enter (incluye lector de código de barras que termina con Enter).
- Carrito con cantidades editables, incremento/decremento y eliminación.
- Cantidades decimales para productos a granel (kg/litro).
- Descuento global en soles.
- Validación de stock y de precio en el servidor local (servicio), no solo en la UI.
- Cobro en efectivo (calcula vuelto), tarjeta o transferencia.
- Comprobante interno con folio, detalle, total, pago y vuelto.
- Generación automática de una boleta PDF A4 en `data/boletas/AAAA/MM/`, con opciones para abrirla, guardar una copia y regenerarla.
- Atajos: `F2` buscar, `F4` cobrar, `F8` limpiar carrito, `Supr` quitar línea.

### 2.2 Caja
- Una sola caja abierta a la vez.
- Apertura con fondo inicial.
- Ingresos y egresos manuales con concepto.
- Resumen de caja: fondo, ventas en efectivo, ingresos, egresos y efectivo esperado.
- Cierre con efectivo contado, diferencia y nota.
- Historial de cierres.
- No se puede vender sin una caja abierta.

### 2.3 Productos
- Alta, edición, activación/desactivación y búsqueda.
- Campos: SKU interno automático, código de barras opcional, nombre, categoría, unidad, costo, precio, stock mínimo y stock inicial.
- Categorías administrables desde el formulario de producto.
- El stock no se modifica desde la edición del producto: se modifica con movimientos de inventario auditables.
- Unicidad de SKU y código de barras.

### 2.4 Inventario
- Vista de existencias con estado (normal, bajo, agotado), valorizado al costo.
- Entrada de mercancía, merma/salida y ajuste a cantidad exacta.
- Historial de movimientos con stock resultante, referencia y fecha.
- Alerta de stock bajo en dashboard e inventario.

### 2.5 Historial de ventas
- Filtros por rango de fechas, estado y texto (folio/producto).
- Detalle de venta con líneas y totales.
- Anulación con motivo; restaura stock.
- Si la venta fue en efectivo y pertenece a una caja ya cerrada, la devolución se registra en la caja abierta actual. Si la venta pertenece a la caja abierta, el cambio de estado la excluye automáticamente del esperado.

### 2.6 Dashboard
- Ventas de hoy (monto y cantidad), ticket promedio.
- Productos con stock bajo/agotado.
- Estado de caja.
- Últimas ventas y accesos rápidos.

### 2.7 Ajustes
- Nombre del negocio, RUC, dirección, teléfono y texto de pie de ticket.
- Los datos se usan en el comprobante.

### Fuera de alcance del MVP
- Facturación electrónica SUNAT.
- Multiusuario, roles y autenticación.
- Compras a proveedores y cuentas por pagar.
- Lector de código de barras por puerto serie (se soporta el modo teclado HID).
- Sincronización en nube o trabajo en red.
- Devoluciones parciales (solo anulación completa).

---

## 3. Decisiones de diseño

| Tema | Decisión | Motivo |
|---|---|---|
| Dinero | Enteros en céntimos | Evita errores de punto flotante. |
| Cantidades | `REAL` | Permite vender 0.25 kg o 1.5 L. |
| Persistencia | SQLite con WAL y claves foráneas | Robusto y adecuado para un solo equipo. |
| Migraciones | Tabla `schema_migrations` + scripts versionados | Evolución segura del esquema. |
| Arquitectura | UI → servicios → repositorios → SQLite | Reglas de negocio testeables sin GUI. |
| Transacciones | `BEGIN IMMEDIATE` en ventas, ajustes y caja | Evita stock negativo y dobles cierres. |
| Precio de venta | Se relee de la BD al cobrar | La UI no puede alterar el precio. |
| Caja | Obligatoria para vender | Trazabilidad del efectivo. |
| Folio | Secuencia diaria `V-AAAAMMDD-####` | Legible para el comercio. |
| Fechas | UTC ISO 8601 en BD; hora local en pantalla | Consistencia y orden correcto. |
| Comprobante | Texto imprimible vía QtPrintSupport | Sin dependencia de impresoras específicas. |
| Boleta PDF | PDF A4 generado con Qt PDF, guardado por año/mes | Copia digital reutilizable sin cambiar el flujo térmico. |

---

## 4. Arquitectura

```text
main.py
└── pos/
    ├── app.py                 # QApplication, fuente, tema, ventana principal
    ├── config.py              # Rutas, constantes, formato de moneda/fecha
    ├── db/
    │   ├── database.py        # Conexión, transacciones, migraciones
    │   ├── migrations.py      # Esquema versionado
    │   └── seed.py            # Categorías/productos demo y ajustes
    ├── repositories/
    │   ├── products.py        # Consultas de productos/categorías
    │   ├── inventory.py       # Movimientos y ajustes
    │   ├── sales.py           # Ventas, líneas y folios
    │   ├── cash.py            # Sesiones y movimientos de caja
    │   ├── settings.py        # Ajustes clave/valor
    │   └── reports.py         # Métricas del dashboard
    ├── services/
    │   ├── errors.py          # Errores de negocio con mensaje en español
    │   ├── products.py        # Validaciones de producto/categoría
    │   ├── inventory.py       # Entradas, mermas y ajustes
    │   ├── sales.py           # Cobro y anulación transaccionales
    │   ├── cash.py            # Apertura, movimientos y cierre
    │   └── reports.py         # Resumen de dashboard/ventas
    └── ui/
        ├── main_window.py
        ├── theme.py
        ├── common.py          # Helpers, tablas, encabezados, dinero
        ├── views/
        │   ├── dashboard_view.py
        │   ├── sale_view.py
        │   ├── products_view.py
        │   ├── inventory_view.py
        │   ├── history_view.py
        │   ├── cash_view.py
        │   └── settings_view.py
        └── dialogs/
            ├── product_dialog.py
            ├── payment_dialog.py
            ├── receipt_dialog.py
            ├── inventory_dialog.py
            ├── sale_detail_dialog.py
            ├── cash_dialogs.py
            └── category_dialog.py

tests/
├── test_products.py
├── test_inventory.py
├── test_sales.py
├── test_cash.py
└── test_ui_smoke.py
```

### Reglas de dependencia
- `ui` puede importar servicios, modelos de lectura y helpers; nunca SQL.
- `services` contiene validaciones y coordina repositorios dentro de transacciones.
- `repositories` solo ejecuta SQL y mapea filas a diccionarios/dataclasses.
- `db` es la única capa que abre conexiones.

---

## 5. Modelo de datos

```text
categories(id, name UNIQUE, created_at)
products(id, sku UNIQUE, barcode UNIQUE NULL, name, category_id FK,
         unit, cost_cents, price_cents, stock REAL, min_stock REAL,
         active, created_at, updated_at)
cash_sessions(id, opened_at, closed_at, opening_cash_cents,
              counted_cash_cents, expected_cash_cents, difference_cents,
              status, notes)
cash_movements(id, cash_session_id FK, kind, amount_cents, concept,
               sale_id FK NULL, created_at)
sales(id, folio UNIQUE, cash_session_id FK, subtotal_cents, discount_cents,
      total_cents, payment_method, cash_received_cents, change_cents,
      status, created_at, cancelled_at, cancel_reason)
sale_items(id, sale_id FK, product_id FK, sku, product_name, unit,
           unit_price_cents, quantity, discount_cents, line_total_cents)
inventory_movements(id, product_id FK, kind, quantity_delta, stock_after,
                    reference, note, created_at)
settings(key PRIMARY KEY, value)
schema_migrations(version PRIMARY KEY, applied_at)
sale_counters(day PRIMARY KEY, next_number)
```

### Invariantes
- `total_cents = subtotal_cents - discount_cents` y nunca es negativo.
- `sum(line_total_cents) = subtotal_cents`.
- `line_total_cents = round(unit_price_cents × quantity) - discount_cents`.
- No se vende un producto inactivo, sin stock o con cantidad ≤ 0.
- No puede existir más de una sesión de caja con estado `abierta`.
- Un ajuste de stock nunca deja existencias negativas.
- Una venta anulada no puede volver a anularse.
- Todo cambio de stock genera un registro en `inventory_movements`.

---

## 6. Flujos críticos

### Cobro
1. La UI envía `[(product_id, quantity)]`, descuento, método, efectivo recibido.
2. El servicio abre `BEGIN IMMEDIATE`.
3. Comprueba caja abierta y carrito válido.
4. Relee productos, precios, estado y stock.
5. Calcula subtotal, descuento y total en céntimos.
6. Valida efectivo/vuelto si corresponde.
7. Inserta venta, obtiene ID y asigna folio diario.
8. Inserta líneas y descuenta stock con verificación atómica.
9. Inserta movimientos de inventario `venta`.
10. Hace commit y devuelve la venta completa para el comprobante.

### Anulación
1. `BEGIN IMMEDIATE`; bloquea y relee la venta.
2. Verifica que esté completada.
3. Marca `cancelada`, guarda fecha y motivo.
4. Devuelve stock y registra movimientos `cancelacion`.
5. Ajusta caja solo si es necesario (ver alcance de caja).
6. Commit.

### Cierre de caja
1. Calcula esperado = fondo + ventas efectivo completadas + ingresos − egresos − devoluciones.
2. Guarda contado y diferencia = contado − esperado.
3. Cambia estado a `cerrada`.
4. Desde ese momento se puede abrir una nueva caja.

---

## 7. Interfaz y experiencia

- Ventana 1360×820, mínima 1120×700, inicia maximizada.
- Barra lateral con navegación: Inicio, Punto de venta, Productos, Inventario, Ventas, Caja, Ajustes.
- Encabezado con nombre del negocio, fecha y estado de caja.
- Paleta clara: fondo marfil, tarjetas blancas, verde profundo para acciones primarias, ámbar para advertencias, rojo para errores.
- Tipografía Segoe UI (fallback al sistema).
- Tablas sin edición directa salvo el carrito; filas alternas y columnas ajustadas.
- Confirmaciones destructivas y mensajes de error claros, sin trazas técnicas.
- Diseño funcional con teclado para el flujo de mostrador.
- Todos los importes se muestran como `S/ 0.00`.

---

## 8. Validaciones y manejo de errores

- SKU/código de barras duplicados → mensaje claro, sin cerrar el formulario.
- Precio de venta > 0; costo y stock ≥ 0; stock mínimo ≥ 0.
- Cantidad de venta > 0 y hasta 3 decimales.
- Descuento entre 0 y subtotal.
- Efectivo recibido ≥ total en pagos en efectivo.
- No se puede abrir caja si ya hay una abierta.
- No se puede cerrar caja sin contar el efectivo.
- Errores de negocio se muestran con `QMessageBox`; errores inesperados se registran en `logs/pos.log`.
- La base de datos se respalda automáticamente antes de aplicar migraciones.

---

## 9. Pruebas y criterios de aceptación

### Automatizadas (unittest, sin dependencias extra)
- Crear/editar/validar productos y unicidad.
- Entrada, merma y ajuste de inventario con historial.
- Venta con descuento, stock, folio y vuelto correctos.
- Venta rechazada sin caja, con stock insuficiente o producto inactivo.
- Anulación restaura stock y no permite doble anulación.
- Apertura/cierre de caja, una sola sesión abierta, arqueo y movimientos.
- Smoke test de la ventana principal con `QT_QPA_PLATFORM=offscreen`.

### Manuales
- Abrir caja → vender 3 productos → cobrar efectivo → ver comprobante → cerrar caja.
- Reiniciar la aplicación y comprobar persistencia.
- Crear producto, ajustar stock y verlo en el POS.
- Anular venta y comprobar stock e historial.

### Criterio de terminado
- `python -m unittest discover -s tests -v` pasa.
- `python main.py` abre la app sin errores.
- README con instalación, uso, backups y estructura.
- Datos demo precargados para probar de inmediato.

---

## 10. Entregables y fases

1. **Fase 1 — Base:** estructura, configuración, migraciones y seed.
2. **Fase 2 — Dominio:** repositorios, servicios y pruebas de negocio.
3. **Fase 3 — UI:** tema, ventana principal, vistas y diálogos.
4. **Fase 4 — Integración:** refresh entre vistas, atajos, comprobante, PDF e impresión.
5. **Fase 5 — Calidad:** pruebas, smoke test, README y verificación final.

### Mejoras futuras sugeridas
Roles y usuarios, compras/proveedores, devoluciones parciales, lector serial, exportación CSV, respaldo desde la app y facturación electrónica.
