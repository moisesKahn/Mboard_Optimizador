from django.core.management.base import BaseCommand
from core.models import Organizacion, Material, Tapacanto


MELAMINAS = [
    # codigo, nombre, espesor(mm), ancho(mm), largo(mm), precio_m2, stock, proveedor
    ("MLM-1830x2500-15", "Melamina Blanca 15mm", 15.0, 1830, 2500, 12500.0, 50, "Proveedor A"),
    ("MLM-1830x2500-18", "Melamina Gris 18mm", 18.0, 1830, 2500, 13900.0, 40, "Proveedor A"),
    ("MLM-1830x2500-25", "Melamina Roble 25mm", 25.0, 1830, 2500, 18200.0, 25, "Proveedor B"),
]

TAPACANTOS = [
    # codigo, nombre, color, ancho(mm), espesor(mm), precio_metro, stock_metros, proveedor
    ("TPC-BLANCO-22x0.5", "Tapacanto Blanco", "Blanco", 22.0, 0.5, 180.0, 500, "Proveedor A"),
    ("TPC-GRIS-22x0.5", "Tapacanto Gris", "Gris", 22.0, 0.5, 195.0, 400, "Proveedor A"),
    ("TPC-ROBLE-22x0.5", "Tapacanto Roble", "Roble", 22.0, 0.5, 210.0, 350, "Proveedor B"),
]


class Command(BaseCommand):
    help = "Seed de materiales (melaminas) y tapacantos base para autoservicio"

    def add_arguments(self, parser):
        parser.add_argument('--org-codigo', default='ORG001', help='Código de organización destino (default ORG001)')
        parser.add_argument('--dry-run', action='store_true', help='Mostrar acciones sin aplicar cambios')

    def handle(self, *args, **opts):
        org_codigo = opts['org_codigo']
        dry = opts['dry_run']
        org = Organizacion.objects.filter(codigo__iexact=org_codigo).first()
        if not org:
            self.stderr.write(self.style.ERROR(f"Organización '{org_codigo}' no encontrada"))
            return

        resumen = { 'materiales_creados': 0, 'materiales_skip': 0, 'tapacantos_creados': 0, 'tapacantos_skip': 0 }

        # Seed materiales
        for codigo, nombre, espesor, ancho, largo, precio_m2, stock, proveedor in MELAMINAS:
            existente = Material.objects.filter(codigo=codigo, organizacion=org).first()
            if existente:
                resumen['materiales_skip'] += 1
                continue
            if dry:
                self.stdout.write(f"[DRY] Crear Material {codigo}")
            else:
                Material.objects.create(
                    codigo=codigo,
                    nombre=nombre,
                    tipo='melamina',
                    espesor=espesor,
                    ancho=ancho,
                    largo=largo,
                    precio_m2=precio_m2,
                    stock=stock,
                    proveedor=proveedor,
                    organizacion=org,
                    activo=True,
                )
                resumen['materiales_creados'] += 1

        # Seed tapacantos
        for codigo, nombre, color, ancho, espesor, precio_metro, stock_metros, proveedor in TAPACANTOS:
            existente = Tapacanto.objects.filter(codigo=codigo, organizacion=org).first()
            if existente:
                resumen['tapacantos_skip'] += 1
                continue
            if dry:
                self.stdout.write(f"[DRY] Crear Tapacanto {codigo}")
            else:
                Tapacanto.objects.create(
                    codigo=codigo,
                    nombre=nombre,
                    color=color,
                    ancho=ancho,
                    espesor=espesor,
                    precio_metro=precio_metro,
                    stock_metros=stock_metros,
                    proveedor=proveedor,
                    organizacion=org,
                    activo=True,
                )
                resumen['tapacantos_creados'] += 1

        self.stdout.write(self.style.SUCCESS("Seed completado" if not dry else "Seed DRY completado"))
        self.stdout.write(str(resumen))