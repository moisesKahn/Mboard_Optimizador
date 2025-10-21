import csv
import sys
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from contextlib import nullcontext

from core.models import Material, Tapacanto, Organizacion


def parse_decimal(value: str, default=None):
    if value is None:
        return default
    s = str(value).strip()
    if s == "":
        return default
    # Aceptar coma o punto decimal
    s = s.replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def parse_int(value: str, default=None):
    if value is None:
        return default
    s = str(value).strip()
    if s == "":
        return default
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return default


class Command(BaseCommand):
    help = (
        "Importa un catálogo desde CSV: materiales o tapacantos, scoping por organización.\n\n"
        "Formato CSV por tipo:\n"
        "- material: codigo,nombre,tipo,espesor,ancho,largo,precio_m2,stock,proveedor,(opcional)organizacion_codigo,organizacion_nombre\n"
        "  tipo ∈ {melamina, mdf, osb, terciado, aglomerado, otro}.\n"
        "- tapacanto: codigo,nombre,color,ancho,espesor,precio_metro,stock_metros,proveedor,(opcional)organizacion_codigo,organizacion_nombre\n\n"
        "Si no vienen columnas de organización, use --org-codigo o --org-nombre.\n"
        "Upsert por (codigo, organizacion). Use --create-only para no actualizar existentes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tipo", choices=["material", "tapacanto"], required=True)
        parser.add_argument("--file", required=True, help="Ruta al CSV (UTF-8)")
        parser.add_argument("--org-codigo", dest="org_codigo", help="Código org por defecto si no viene en CSV")
        parser.add_argument("--org-nombre", dest="org_nombre", help="Nombre org por defecto si no viene en CSV")
        parser.add_argument("--delimiter", default=",", help="Delimitador CSV (por defecto ,)")
        parser.add_argument("--dry-run", action="store_true", help="Valida sin guardar cambios")
        parser.add_argument("--create-only", action="store_true", help="Solo crea, no actualiza existentes")

    def handle(self, *args, **opts):
        tipo = opts["tipo"]
        path = opts["file"]
        delimiter = opts["delimiter"]
        dry_run = opts["dry_run"]
        create_only = opts["create_only"]
        org_codigo_def = (opts.get("org_codigo") or "").strip() or None
        org_nombre_def = (opts.get("org_nombre") or "").strip() or None

        if not org_codigo_def and not org_nombre_def:
            self.stdout.write("Nota: No se especificó organización por defecto; se esperará por fila en CSV si vienen columnas organizacion_codigo/organizacion_nombre.")

        # Validar archivo
        try:
            f = open(path, "r", encoding="utf-8")
        except OSError as e:
            raise CommandError(f"No se pudo abrir el archivo CSV: {e}")

        with f:
            reader = csv.DictReader(f, delimiter=delimiter)
            if tipo == "material":
                required = ["codigo", "nombre", "tipo", "espesor", "ancho", "largo", "precio_m2", "stock"]
            else:
                required = ["codigo", "nombre", "color", "ancho", "espesor", "precio_metro", "stock_metros"]

            missing = [h for h in required if h not in reader.fieldnames]
            if missing:
                raise CommandError(f"Faltan columnas requeridas en CSV: {', '.join(missing)}")

            allowed_tipos = {k for k, _ in getattr(Material, "TIPOS_MATERIAL", [])}

            created = 0
            updated = 0
            skipped = 0
            errors = 0

            # Usar una transacción si no es dry-run
            context = transaction.atomic() if not dry_run else nullcontext()

            with context:
                for i, row in enumerate(reader, start=2):  # start=2 por encabezado
                    # Resolver organización
                    org_codigo = (row.get("organizacion_codigo") or org_codigo_def or "").strip() or None
                    org_nombre = (row.get("organizacion_nombre") or org_nombre_def or "").strip() or None
                    org = None
                    if org_codigo:
                        org = Organizacion.objects.filter(codigo=org_codigo).first()
                    if not org and org_nombre:
                        org = Organizacion.objects.filter(nombre=org_nombre).first()
                    if not org:
                        self.stderr.write(f"[L{i}] Organización no encontrada (codigo={org_codigo!r}, nombre={org_nombre!r}). Fila omitida.")
                        skipped += 1
                        continue

                    try:
                        if tipo == "material":
                            codigo = (row.get("codigo") or "").strip()
                            nombre = (row.get("nombre") or "").strip()
                            tipo_val = (row.get("tipo") or "").strip().lower()
                            if allowed_tipos and tipo_val not in allowed_tipos:
                                # intentar mapear por etiqueta humana
                                etiqueta_map = {v.lower(): k for k, v in getattr(Material, "TIPOS_MATERIAL", [])}
                                tipo_val = etiqueta_map.get(tipo_val, tipo_val)
                            if allowed_tipos and tipo_val not in allowed_tipos:
                                raise ValueError(f"tipo inválido: {row.get('tipo')!r}")
                            espesor = parse_decimal(row.get("espesor"))
                            ancho = parse_int(row.get("ancho"))
                            largo = parse_int(row.get("largo"))
                            precio_m2 = parse_decimal(row.get("precio_m2"))
                            stock = parse_int(row.get("stock"), 0) or 0
                            proveedor = (row.get("proveedor") or "").strip() or None

                            if not codigo or not nombre:
                                raise ValueError("codigo y nombre son requeridos")
                            if not espesor or not ancho or not largo or not precio_m2:
                                raise ValueError("espesor, ancho, largo y precio_m2 son requeridos y numéricos")
                            if ancho <= 0 or largo <= 0:
                                raise ValueError("ancho y largo deben ser positivos")

                            # upsert por (codigo, organizacion)
                            defaults = {
                                "nombre": nombre,
                                "tipo": tipo_val,
                                "espesor": espesor,
                                "ancho": ancho,
                                "largo": largo,
                                "precio_m2": precio_m2,
                                "stock": stock,
                                "proveedor": proveedor,
                                "organizacion": org,
                                "activo": True,
                            }
                            obj, was_created = Material.objects.get_or_create(
                                codigo=codigo, organizacion=org, defaults=defaults
                            )
                            if was_created:
                                created += 1
                            else:
                                if create_only:
                                    skipped += 1
                                else:
                                    for k, v in defaults.items():
                                        setattr(obj, k, v)
                                    obj.save()
                                    updated += 1

                        else:  # tapacanto
                            codigo = (row.get("codigo") or "").strip()
                            nombre = (row.get("nombre") or "").strip()
                            color = (row.get("color") or "").strip()
                            ancho = parse_decimal(row.get("ancho"))
                            espesor = parse_decimal(row.get("espesor"))
                            precio_metro = parse_decimal(row.get("precio_metro"))
                            stock_metros = parse_int(row.get("stock_metros"), 0) or 0
                            proveedor = (row.get("proveedor") or "").strip() or None

                            if not codigo or not nombre:
                                raise ValueError("codigo y nombre son requeridos")
                            if not color:
                                raise ValueError("color es requerido")
                            if not ancho or not espesor or not precio_metro:
                                raise ValueError("ancho, espesor y precio_metro son requeridos y numéricos")

                            defaults = {
                                "nombre": nombre,
                                "color": color,
                                "ancho": ancho,
                                "espesor": espesor,
                                "precio_metro": precio_metro,
                                "stock_metros": stock_metros,
                                "proveedor": proveedor,
                                "organizacion": org,
                                "activo": True,
                            }
                            obj, was_created = Tapacanto.objects.get_or_create(
                                codigo=codigo, organizacion=org, defaults=defaults
                            )
                            if was_created:
                                created += 1
                            else:
                                if create_only:
                                    skipped += 1
                                else:
                                    for k, v in defaults.items():
                                        setattr(obj, k, v)
                                    obj.save()
                                    updated += 1

                    except Exception as e:
                        errors += 1
                        self.stderr.write(f"[L{i}] Error: {e}")

                if dry_run:
                    # Forzar rollback
                    raise CommandError(
                        f"Dry-run: created={created}, updated={updated}, skipped={skipped}, errors={errors} (no se guardaron cambios)"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Importación finalizada: created={created}, updated={updated}, skipped={skipped}, errors={errors}"
            )
        )
