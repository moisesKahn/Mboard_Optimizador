# Importación de Materiales (Tableros) y Tapacantos

Este documento describe el formato de archivos CSV aceptados para importar Tableros (modelo `Material`) y Tapacantos (modelo `Tapacanto`).

Notas generales:
- Codificación recomendada: UTF-8.
- Separador: coma (,).
- La primera fila debe ser de cabeceras.
- Los nombres de columnas no son sensibles a mayúsculas/minúsculas.
- Para Super Admin, si no se especifica organización por UI, se asignará a la primera organización existente (comportamiento actual). Para usuarios con organización, se importa siempre a su organización.

## Tableros (Material)

Columnas requeridas:
- codigo (string) – Identificador único por organización.
- nombre (string)
- tipo (string) – uno de: melamina, mdf, osb, terciado, aglomerado, otro
- espesor_mm (float)
- ancho_mm (float) – Debe ser la medida mayor
- largo_mm (float) – Debe ser la medida menor

Columnas opcionales:
- precio_m2 (float) – precio por metro cuadrado
- precio_tablero (float) – si no se provee `precio_m2`, se calculará a partir de este valor y el área
- stock (int)
- proveedor (string)

Ejemplo CSV (tableros):

codigo,nombre,tipo,espesor_mm,ancho_mm,largo_mm,precio_m2,stock,proveedor
MEL-01,Melamina Blanco,melamina,18,2440,1830,12.5,100,Proveedor A
MDF-15,MDF Crudo,mdf,15,2440,1830,10,50,Proveedor B
OSB-09,OSB Constructivo,osb,9,2440,1220,,30,Proveedor C

Notas:
- Si se incluye `precio_tablero` en vez de `precio_m2`, el sistema calcula `precio_m2 = precio_tablero / area`.
- El par (codigo, organizacion) es único: si ya existe, se actualiza (vía update_or_create).
- Validación: ancho debe ser la medida mayor, y ambas dimensiones > 0.

## Tapacantos

Columnas requeridas:
- codigo (string)
- nombre (string)
- color (string)
- ancho_mm (float)
- espesor_mm (float)
- valor_por_metro (float) – precio por metro

Columnas opcionales:
- stock_metros (float)
- proveedor (string)

Ejemplo CSV (tapacantos):

codigo,nombre,color,ancho_mm,espesor_mm,valor_por_metro,stock_metros,proveedor
TC-01,Tapacanto Blanco,Blanco,22,0.45,0.12,500,Proveedor A
TC-02,Tapacanto Roble,Roble,19,0.45,0.14,300,Proveedor B

## Endpoints de importación

- Tableros: POST a `/materiales/tableros/importar`
  - Cuerpo: texto CSV (no multipart en la versión actual)
- Tapacantos: POST a `/materiales/tapacantos/importar`
  - Cuerpo: texto CSV

Respuestas típicas:
- `{ success: true, creados: N, actualizados: M, errores: [] }`
- En caso de error de formato: `{ success: false, message: "Columnas requeridas faltantes" }`

## Consideraciones de organización

- Usuarios con organización asignada: todos los registros importados se asignan a su organización.
- Super Admin (organización global): actualmente se asigna a la primera organización existente. En escenarios multi-tenant con múltiples organizaciones, conviene implementar una selección de organización en UI antes de importar.

## Validaciones importantes
- `ancho_mm` debe ser la medida mayor. Si el largo supera al ancho, la importación fallará con mensaje indicativo.
- `tipo` debe estar entre los valores soportados.
- Para tableros, si faltan columnas requeridas, la importación retorna error (400).
- Para tapacantos, mismo criterio de columnas requeridas.
