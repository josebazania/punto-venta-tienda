from pathlib import Path

from openpyxl import Workbook, load_workbook

from pos.services.errors import ValidationError
from pos.services.product_import import export_products, import_products, save_template
from tests.base import ServiceTestCase


class ProductImportTests(ServiceTestCase):
    def test_import_creates_valid_rows_and_reports_errors(self):
        path = Path(self._tmp.name) / "productos.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["nombre", "precio", "codigo", "stock", "categoria"])
        category = self.ctx.products.categories()[0]["name"]
        sheet.append(["Arroz", 5, "AR01", 3, category])
        sheet.append(["Duplicado", 2, "AR01", 0, category])
        sheet.append(["Precio inválido", 0, "XX02", 0, category])
        book.save(path)
        book.close()
        count, errors = import_products(path, self.ctx.products)
        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("Fila 3:"))
        product = self.ctx.products.find_by_code("AR01")
        self.assertEqual(product["price_cents"], 500)
        self.assertEqual(product["stock"], 3)
        self.assertEqual(len(self.ctx.inventory.list_movements(product_id=product["id"])), 1)

    def test_template_and_missing_header(self):
        path = Path(self._tmp.name) / "plantilla.xlsx"
        save_template(path)
        self.assertEqual(import_products(path, self.ctx.products), (0, []))
        book = Workbook()
        book.active.append(["nombre"])
        book.save(path)
        book.close()
        with self.assertRaises(ValidationError):
            import_products(path, self.ctx.products)

    def test_export_includes_inactive_products_and_preserves_codes(self):
        product_id = self.make_product(name="=Producto", barcode="00123456789", price_cents=525, stock=4)
        self.ctx.products.set_active(product_id, False)
        path = Path(self._tmp.name) / "export.xlsx"
        self.assertEqual(export_products(path, self.ctx.products), 1)
        book = load_workbook(path, data_only=False)
        sheet = book.active
        self.assertEqual(sheet["A2"].value, "=Producto")
        self.assertEqual(sheet["A2"].data_type, "s")
        self.assertEqual(sheet["B2"].value, 5.25)
        self.assertEqual(sheet["D2"].value, "00123456789")
        self.assertEqual(sheet["H2"].value, 4)
        self.assertEqual(sheet["J2"].value, "Inactivo")
        book.close()
