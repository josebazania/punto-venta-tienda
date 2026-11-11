# Abarrotes POS

Aplicación de escritorio para gestionar las ventas y el inventario de una tienda de abarrotes. Funciona con datos locales en SQLite y está orientada a negocios que trabajan en soles peruanos.

El proyecto utiliza Python, PySide6, SQLite y openpyxl. La interfaz está en español y permite trabajar sin conexión a internet una vez instaladas las dependencias.

> **Comprobantes:** los PDF y tickets generados son comprobantes internos. La aplicación no emite boletas ni facturas electrónicas SUNAT.

![Pantalla de inicio de Abarrotes POS](docs/screenshots/resumen.png)

## Funciones

- **Punto de venta:** búsqueda por nombre, código interno o código de barras; carrito, cantidades decimales y descuentos.
- **Cobros:** efectivo, tarjeta, transferencia y Yape. Los pagos no efectivos se incluyen en las ventas, pero no en el efectivo esperado de caja.
- **Caja:** apertura, movimientos, arqueo y cierre. Se requiere una caja abierta para registrar ventas.
- **Productos e inventario:** catálogo, categorías, precios, stock mínimo, entradas, mermas, ajustes y movimientos.
- **Excel:** plantilla, importación de nuevos productos y exportación del catálogo en `.xlsx`.
- **Historial de ventas:** búsqueda, filtros por fecha y estado, accesos rápidos a hoy, ayer, esta semana y este mes, y anulación de ventas.
- **Comprobantes:** impresión y PDF para papel térmico de 80 mm. Desde el detalle de una venta se puede imprimir el ticket o abrir su PDF.
- **Estadísticas:** ventas, ticket promedio, métodos de pago, productos más vendidos y evolución diaria, con periodos de 7 días, 30 días o mes actual.
- **Respaldo:** copia de la base de datos desde la interfaz y respaldo automático antes de una migración.

![Pantalla de punto de venta](docs/screenshots/punto-venta.png)

Las capturas del repositorio son ilustrativas y pueden no reflejar los cambios más recientes de la interfaz.

## Requisitos

- Python 3.10 o superior y un entorno gráfico compatible con Qt.
- Windows 10/11 para el ejecutable de Windows. El código fuente también puede ejecutarse en Linux o macOS con sus dependencias gráficas instaladas.
- PySide6 y openpyxl, instalados mediante `requirements.txt`.
- Para imprimir, una impresora configurada en el sistema operativo. El PDF está diseñado para papel térmico de 80 mm.

## Instalación desde el código fuente

Clona este repositorio desde GitHub y abre una terminal en la carpeta del proyecto. Usa la URL que proporciona el botón **Code** de GitHub:

```bash
git clone <URL-DEL-REPOSITORIO>
cd <carpeta-del-repositorio>
```

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

También puedes iniciar con `iniciar.bat`; si existe `.venv`, el archivo utiliza ese entorno. Si PowerShell impide activar el entorno virtual, puedes ejecutarlo sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Linux y macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

### Ejecutable para Windows

El repositorio no incluye los archivos generados en `dist/`. Si el propietario publica una versión en **Releases**, descarga el ejecutable de esa publicación. Un ejecutable empaquetado incluye Python y sus librerías; no necesitas instalarlos por separado en el equipo donde lo uses.

Para generar un ejecutable en Windows con Python 3.12, desde un entorno virtual con las dependencias instaladas:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name AbarrotesPOS --icon pos/ui/assets/icono.ico --add-data "pos/ui/assets;pos/ui/assets" main.py
```

El resultado se guarda en `dist\AbarrotesPOS.exe`. La compilación se realiza en Windows para Windows; prueba el archivo resultante antes de distribuirlo. PyInstaller es una herramienta de compilación y no está incluido en `requirements.txt`.

## Primeros pasos

1. Inicia la aplicación y revisa **Ajustes → Datos del negocio** para configurar el nombre, RUC, dirección, teléfono y mensaje del comprobante.
2. Ve a **Productos** para revisar o registrar el catálogo. En el primer inicio se cargan productos de demostración por defecto.
3. En **Caja**, abre un turno e ingresa el fondo inicial.
4. En **Punto de venta**, busca los productos, agrégalos al carrito y selecciona **Cobrar**. Elige el método de pago y confirma la venta.
5. Abre o imprime el comprobante. Al terminar el turno, utiliza **Caja → Cerrar caja** para realizar el arqueo.

Para iniciar una base nueva sin los productos de demostración, establece la variable antes del primer inicio de esa base:

```powershell
$env:POS_SEED_DEMO = "0"
python main.py
```

En Linux o macOS: `POS_SEED_DEMO=0 python main.py`. Esta opción no elimina productos ya registrados. Se crean las categorías y ajustes iniciales.

### Atajos del punto de venta

| Tecla | Acción |
| --- | --- |
| `F2` | Enfocar la búsqueda de productos |
| `F4` | Abrir el cobro |
| `F8` | Vaciar el carrito |
| `Supr` | Quitar el producto seleccionado del carrito |
| `Enter` en búsqueda | Agregar el código exacto o el único resultado |

Un lector de código de barras que funcione como teclado puede utilizarse en el campo de búsqueda.

## Productos y Excel

En **Productos → Plantilla Excel** puedes guardar una plantilla `.xlsx`. Completa una fila por producto con los siguientes encabezados:

| Columna | Contenido |
| --- | --- |
| `nombre` | Nombre del producto; obligatorio. |
| `precio` | Precio de venta en soles; obligatorio y mayor que cero. |
| `codigo` | Código interno; si está vacío, se genera uno. |
| `codigo_barras` | Código de barras opcional. Usa formato de texto en Excel para conservar ceros iniciales. |
| `categoria` | Nombre de una categoría existente; opcional. |
| `unidad` | `pieza`, `kg`, `litro`, `paquete`, `caja` o `bolsa`; por defecto, `pieza`. |
| `costo` | Costo en soles; por defecto, cero. |
| `stock` | Stock inicial; por defecto, cero. |
| `stock_minimo` | Cantidad mínima para alertas; por defecto, cero. |

Selecciona **Importar Excel** para procesar el archivo. Las filas válidas se crean y las filas con errores se omiten y se detallan en el resultado. No se admiten fórmulas. La importación **no actualiza productos existentes**; antes de reintentar, retira las filas que ya se importaron. El stock inicial genera un movimiento de inventario.

Con **Exportar Excel** se guarda el catálogo completo, incluidos los productos inactivos, independientemente de los filtros visibles. El archivo incluye una columna informativa `estado` y comparte las demás columnas con la plantilla. Importarlo crea productos nuevos; no es una función de actualización masiva.

## Ventas, comprobantes y estadísticas

En **Ventas**, selecciona una venta y usa **Generar PDF** o haz doble clic para abrir su detalle. Desde el detalle puedes seleccionar **Abrir PDF** o **Imprimir comprobante**. El PDF se guarda por año y mes; si falta, el programa puede generarlo nuevamente. Las ventas anuladas se identifican como tales.

Los PDF tienen un ancho de 80 mm y una altura ajustada al contenido. Al imprimir, selecciona la impresora y el tamaño de papel adecuado en el diálogo del sistema. Los PDF se pueden localizar desde **Ajustes → Abrir boletas PDF**.

La sección **Estadísticas** utiliza ventas completadas y excluye las anuladas. Muestra hasta cinco productos según la cantidad vendida y, en la evolución diaria, hasta los siete días más recientes del periodo que tuvieron ventas.

## Datos, copias y configuración

La ubicación predeterminada depende de cómo se ejecute la aplicación:

| Ejecución | Base de datos | PDF y respaldos | Registros |
| --- | --- | --- | --- |
| Desde el código fuente | `data/pos.db` | `data/boletas/` y `data/backups/` | `logs/` |
| Ejecutable Windows | `%LOCALAPPDATA%\AbarrotesPOS\data\pos.db` | `%LOCALAPPDATA%\AbarrotesPOS\data\boletas\` y `data\backups\` | `%LOCALAPPDATA%\AbarrotesPOS\logs\` |

En **Ajustes → Información del sistema** se muestra la ruta real de la base; **Abrir datos** abre la carpeta que la contiene. Cada usuario de Windows tiene su propia carpeta local. Mover solamente el ejecutable a otro equipo no transfiere sus datos.

Usa **Ajustes → Crear respaldo** para guardar una copia SQLite. El respaldo no incluye los PDF: copia también la carpeta de boletas si necesitas conservar esos archivos. Antes de restaurar una copia o manipular la base manualmente, cierra la aplicación y conserva una copia de seguridad de los datos actuales. Los PDF pueden regenerarse desde el historial, utilizando los datos del negocio configurados en ese momento.

Se pueden definir estas variables de entorno antes de iniciar:

| Variable | Función |
| --- | --- |
| `POS_DB_PATH` | Ruta personalizada del archivo SQLite. |
| `POS_PDF_DIR` | Carpeta donde se guardan los PDF. |
| `POS_SEED_DEMO` | Usa `0`, `false` o `no` para desactivar la carga de demostración. |

Ejemplo en PowerShell:

```powershell
$env:POS_DB_PATH = "D:\Datos\abarrotes.db"
$env:POS_PDF_DIR = "D:\Datos\boletas"
python main.py
```

Las bases de datos, respaldos, registros, entornos virtuales y compilaciones están excluidos por `.gitignore`. Revisa siempre los archivos que vas a publicar y evita subir información real de clientes o ventas.

## Estructura

```text
main.py                 Entrada de la aplicación
iniciar.bat             Lanzador para Windows
requirements.txt        Dependencias de ejecución
pos/config.py           Configuración, rutas y constantes
pos/db/                 Conexiones, migraciones y datos iniciales
pos/repositories/       Consultas y acceso a SQLite
pos/services/           Reglas de negocio, reportes y PDF
pos/ui/                 Ventanas, vistas, diálogos y recursos gráficos
tests/                  Pruebas de servicios e interfaz
docs/screenshots/       Capturas ilustrativas
```

La arquitectura sigue el flujo **interfaz → servicios → repositorios → SQLite**. Los importes se almacenan en céntimos enteros. El inventario se valida al vender y sus cambios quedan registrados como movimientos.

## Pruebas

En una terminal con las dependencias instaladas:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

En Linux o macOS:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

Las pruebas cubren, entre otros componentes, productos, inventario, ventas, caja, comprobantes, PDF, importación y exportación de Excel, migraciones y carga de vistas.

## Alcance actual

- No realiza facturación electrónica SUNAT ni se integra con pasarelas de pago: Yape se registra como método de pago, pero la aplicación no verifica el abono automáticamente.
- No incluye cuentas de usuario, roles ni sincronización en red o en la nube.
- No gestiona varias cajas abiertas simultáneamente ni devoluciones parciales.
- Los datos se guardan localmente; organiza copias de seguridad periódicas según las necesidades del negocio.

## Licencia

Este repositorio todavía no incluye un archivo de licencia. La disponibilidad pública del código no concede por sí sola una licencia de uso, modificación o distribución; consulta al propietario para conocer las condiciones aplicables.

