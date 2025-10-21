# Importación de Catálogo (Materiales y Tapacantos)

Este proyecto incluye un comando de gestión para importar catálogos desde archivos CSV por organización.

Comando:

- Materiales:
  python manage.py import_catalogo_csv --tipo material --file "ruta/materiales.csv" --org-codigo ORG_GENERAL

- Tapacantos:
  python manage.py import_catalogo_csv --tipo tapacanto --file "ruta/tapacantos.csv" --org-codigo ORG_GENERAL

Parámetros útiles:
- --dry-run: valida sin guardar cambios.
- --create-only: crea nuevos, no actualiza existentes.
- --delimiter ";": si el CSV usa punto y coma.
- --org-nombre "Mi Organización": alternativa a --org-codigo.

Formato CSV (UTF-8, encabezado en la primera fila):

Materiales (columnas requeridas):
- codigo, nombre, tipo, espesor, ancho, largo, precio_m2, stock, proveedor (opcional), organizacion_codigo (opcional), organizacion_nombre (opcional)
  - tipo: melamina | mdf | osb | terciado | aglomerado | otro
  - espesor: número (se admite coma o punto decimal)
  - ancho/largo: milímetros (enteros positivos). El modelo normaliza para que ancho >= largo.

Tapacantos (columnas requeridas):
- codigo, nombre, color, ancho, espesor, precio_metro, stock_metros, proveedor (opcional), organizacion_codigo (opcional), organizacion_nombre (opcional)

Ejemplos: ver `Django/sample_data/materiales_template.csv` y `Django/sample_data/tapacantos_template.csv`.

Notas:
- El upsert se hace por (codigo, organización). Si el registro ya existe y no usas `--create-only`, se actualizará.
- Si el CSV no trae columnas de organización, usa `--org-codigo` o `--org-nombre` para aplicarlo a todas las filas.
- Errores por fila se reportan con el número de línea `[L#]`.
