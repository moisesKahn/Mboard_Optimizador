from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Organizacion, Material, Tapacanto

class Command(BaseCommand):
    help = "Migra/replica Materiales y Tapacantos a todas las organizaciones. Soporta dry-run y filtros."

    def add_arguments(self, parser):
        parser.add_argument('--only-null', action='store_true', help='Solo asignar/migrar los que no tienen organizacion (organizacion IS NULL)')
        parser.add_argument('--update', action='store_true', help='Si existe el codigo en la organizacion, actualizar campos en vez de saltar')
        parser.add_argument('--exclude-general', action='store_true', help='Excluir organizaciones is_general=True')
        parser.add_argument('--dry-run', action='store_true', help='No escribe cambios, solo reporta')

    def handle(self, *args, **opts):
        only_null = opts['only_null']
        do_update = opts['update']
        exclude_general = opts['exclude_general']
        dry = opts['dry_run']

        orgs_qs = Organizacion.objects.filter(activo=True)
        if exclude_general:
            orgs_qs = orgs_qs.filter(is_general=False)
        orgs = list(orgs_qs)
        self.stdout.write(self.style.NOTICE(f"Organizaciones destino: {len(orgs)}"))

        mats_qs = Material.objects.all()
        taps_qs = Tapacanto.objects.all()
        if only_null:
            mats_qs = mats_qs.filter(organizacion__isnull=True)
            taps_qs = taps_qs.filter(organizacion__isnull=True)

        mats = list(mats_qs)
        taps = list(taps_qs)
        self.stdout.write(self.style.NOTICE(f"Materiales base: {len(mats)} | Tapacantos base: {len(taps)}"))

        created_m = updated_m = skipped_m = 0
        created_t = updated_t = skipped_t = 0

        @transaction.atomic
        def run():
            nonlocal created_m, updated_m, skipped_m, created_t, updated_t, skipped_t
            for org in orgs:
                # Material
                for m in mats:
                    defaults = dict(
                        nombre=m.nombre,
                        tipo=m.tipo,
                        espesor=m.espesor,
                        ancho=m.ancho,
                        largo=m.largo,
                        precio_m2=m.precio_m2,
                        stock=m.stock,
                        proveedor=m.proveedor,
                        activo=m.activo,
                    )
                    obj = Material.objects.filter(codigo=m.codigo, organizacion=org).first()
                    if obj:
                        if do_update:
                            for k, v in defaults.items():
                                setattr(obj, k, v)
                            obj.save()
                            updated_m += 1
                        else:
                            skipped_m += 1
                    else:
                        Material.objects.create(organizacion=org, codigo=m.codigo, **defaults)
                        created_m += 1
                # Tapacanto
                for t in taps:
                    defaults = dict(
                        nombre=t.nombre,
                        color=t.color,
                        ancho=t.ancho,
                        espesor=t.espesor,
                        precio_metro=t.precio_metro,
                        stock_metros=t.stock_metros,
                        proveedor=t.proveedor,
                        activo=t.activo,
                    )
                    obj = Tapacanto.objects.filter(codigo=t.codigo, organizacion=org).first()
                    if obj:
                        if do_update:
                            for k, v in defaults.items():
                                setattr(obj, k, v)
                            obj.save()
                            updated_t += 1
                        else:
                            skipped_t += 1
                    else:
                        Tapacanto.objects.create(organizacion=org, codigo=t.codigo, **defaults)
                        created_t += 1

        if dry:
            self.stdout.write(self.style.WARNING('DRY-RUN: No se harán cambios.'))
            # Ejecutar dentro de transacción y deshacer al final
            try:
                with transaction.atomic():
                    run()
                    raise RuntimeError('Dry-run rollback')
            except RuntimeError:
                pass
        else:
            run()

        self.stdout.write(self.style.SUCCESS(
            f"Materiales -> creados:{created_m} actualizados:{updated_m} omitidos:{skipped_m}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Tapacantos -> creados:{created_t} actualizados:{updated_t} omitidos:{skipped_t}"
        ))
