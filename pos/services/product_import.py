from __future__ import annotations

from pathlib import Path
from copy import copy

from openpyxl import Workbook, load_workbook

from pos import config
from pos.services.errors import POSError, ValidationError

COLUMNS = ("nombre", "precio", "codigo", "codigo_barras", "categoria", "unidad", "costo", "stock", "stock_minimo")


def save_template(path: str | Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Productos"
    sheet.append(COLUMNS)
    sheet.freeze_panes = "A2"
    for column in sheet.columns:
        font = copy(column[0].font)
        font.bold = True
        column[0].font = font
        sheet.column_dimensions[column[0].column_letter].width = 20
    workbook.save(path)
    workbook.close()



def export_products(path: str | Path, products) -> int:
    """Exporta el catálogo completo, con importes en soles y códigos como texto."""
    rows = products.list_all()
    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.title = "Productos"
        sheet.append((*COLUMNS, "estado"))
        sheet.freeze_panes = "A2"
        for product in rows:
            values = (
                product["name"], product["price_cents"] / 100,
                product["sku"], product.get("barcode") or "",
                product.get("category_name") or "", product["unit"],
                product["cost_cents"] / 100, product["stock"],
                product["min_stock"], "Activo" if product["active"] else "Inactivo",
            )
            sheet.append(values)
            # Los textos del catálogo no deben interpretarse como fórmulas en Excel.
            for index in (1, 3, 4, 5, 6, 10):
                cell = sheet.cell(sheet.max_row, index)
                cell.data_type = "s"
            for index in (2, 7):
                sheet.cell(sheet.max_row, index).number_format = "0.00"
        for column in sheet.columns:
            font = copy(column[0].font)
            font.bold = True
            column[0].font = font
            sheet.column_dimensions[column[0].column_letter].width = 20
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(path)
    finally:
        workbook.close()
    return len(rows)


def import_products(path: str | Path, products) -> tuple[int, list[str]]:
    """Importa filas independientes; devuelve el número creado y errores por fila."""
    try:
        workbook = load_workbook(path, read_only=True, data_only=False)
    except Exception as exc:
        raise ValidationError(f"No se pudo abrir el archivo Excel: {exc}") from exc
    try:
        sheet = workbook.active
        rows = sheet.iter_rows()
        header = next(rows, ())
        names = [str(cell.value or "").strip().lower() for cell in header]
        if len(names) != len(set(name for name in names if name)) + names.count(""):
            raise ValidationError("La hoja contiene encabezados repetidos.")
        missing = [name for name in ("nombre", "precio") if name not in names]
        if missing:
            raise ValidationError("Faltan columnas obligatorias: " + ", ".join(missing))
        categories = {c["name"].strip().casefold(): c["id"] for c in products.categories()}
        count = 0
        errors = []
        for number, cells in enumerate(rows, start=2):
            if all(cell.value is None for cell in cells):
                continue
            row = {name: cells[index] for index, name in enumerate(names) if name and index < len(cells)}
            try:
                if any(cell.data_type == "f" for cell in row.values()):
                    raise ValidationError("Las fórmulas no están admitidas; copia sus valores.")
                def value(name, default=None):
                    cell = row.get(name)
                    return default if cell is None or cell.value is None else cell.value
                category = str(value("categoria", "")).strip()
                if category and category.casefold() not in categories:
                    raise ValidationError(f"La categoría «{category}» no existe.")
                def money(name, default):
                    # Los importes de Excel están expresados en soles, incluso si son enteros.
                    return config.parse_money(str(value(name, default)))
                data = {
                    "name": value("nombre", ""), "sku": value("codigo", ""),
                    "barcode": value("codigo_barras", ""),
                    "category_id": categories.get(category.casefold()) if category else None,
                    "unit": value("unidad", "pieza"), "price_cents": money("precio", ""),
                    "cost_cents": money("costo", 0), "stock": value("stock", 0),
                    "min_stock": value("stock_minimo", 0),
                }
                products.create(data)
                count += 1
            except (POSError, ValueError, TypeError, OverflowError) as exc:
                errors.append(f"Fila {number}: {exc}")
        return count, errors
    finally:
        workbook.close()
