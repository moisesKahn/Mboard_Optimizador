Formato de importación — Tableros y Tapacantos

Resumen rápido
- Codificación: UTF-8 (recomendado)
- Delimitador: coma (CSV)
- Las cabeceras pueden venir en mayúsculas/minúsculas; el importador verifica `lower()`.

1) Tableros (importar_tableros_csv)
Cabeceras requeridas (insensibles a mayúsculas):
- codigo
- nombre
- tipo (ej: mdf, melamina, etc.)
- espesor_mm
- ancho_mm  (debe ser la medida mayor)
- largo_mm  (medida menor)

Campos opcionales útiles:
- precio_m2  (float)
- precio_tablero (float)  <-- si se provee, el importador calculará precio_m2 por área
- stock (int)
- proveedor (string)

Ejemplo (CSV):
codigo,nombre,tipo,espesor_mm,ancho_mm,largo_mm,precio_m2,stock
TAB-001,Melamina Blanca,melamina,18,2750,1830,15000,10

Notas:
- El importador valida que `ancho_mm` sea la medida mayor; si no lo es, fallará con error indicando la línea.
- El campo `codigo` se usa para `update_or_create` junto con la organización.

2) Tapacantos (importar_tapacantos_csv)
Cabeceras requeridas (insensibles a mayúsculas):
- codigo
- nombre
- color
- ancho_mm
- espesor_mm
- valor_por_metro

Campos opcionales:
- stock_metros (float)
- proveedor

Ejemplo (CSV):
codigo,nombre,color,ancho_mm,espesor_mm,valor_por_metro,stock_metros
TAP-001,ABS Blanco,#FFFFFF,22,1.0,1200,50

Uso desde cURL (ejemplo):
curl -X POST "https://<tu-host>/materiales/tableros/importar" \
  -H "Authorization: Token <tu-token>" \
  -H "Content-Type: text/csv" \
  --data-binary @tableros.csv

Notas finales
- Asegúrate de pertenecer a la organización correcta o ser Super Admin antes de importar (el importador asigna `organizacion` automáticamente según el perfil del usuario).
- Si necesitas formato Excel (.xlsx), conviértelo a CSV (UTF-8) antes de subir o adapta el endpoint para parsear xlsx.
