from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import Organizacion, UsuarioPerfilOptimizador


class Command(BaseCommand):
    help = "Crear usuarios por organización para roles Supervisor y Autoservicio si no existen"

    def add_arguments(self, parser):
        parser.add_argument('--supervisor-prefix', default='supervisor_', help='Prefijo para username supervisor')
        parser.add_argument('--autoservicio-prefix', default='autoservicio_', help='Prefijo para username autoservicio')
        parser.add_argument('--password', default='Cambiar123!', help='Contraseña inicial para ambos usuarios')
        parser.add_argument('--dry-run', action='store_true', help='Solo mostrar acciones sin crear usuarios')

    def handle(self, *args, **options):
        sup_pref = options['supervisor_prefix']
        auto_pref = options['autoservicio_prefix']
        password = options['password']
        dry = options['dry_run']

        resumen = []
        created_count = 0
        skipped_count = 0

        for org in Organizacion.objects.filter(activo=True).order_by('id'):
            # Supervisor
            username_sup = f"{sup_pref}{org.codigo.lower()}"
            username_auto = f"{auto_pref}{org.codigo.lower()}"

            with transaction.atomic():
                # Crear supervisor si falta
                if not User.objects.filter(username=username_sup).exists():
                    if dry:
                        resumen.append(f"[DRY] Crear supervisor {username_sup} para org {org.codigo}")
                    else:
                        user_sup = User.objects.create_user(username=username_sup, password=password)
                        user_sup.first_name = 'Supervisor'
                        user_sup.last_name = org.nombre[:40]
                        user_sup.save()
                        UsuarioPerfilOptimizador.objects.create(user=user_sup, rol='supervisor', organizacion=org)
                        created_count += 1
                        resumen.append(f"OK Supervisor {username_sup}")
                else:
                    skipped_count += 1
                    resumen.append(f"Skip supervisor {username_sup} (ya existe)")

                # Crear autoservicio si falta
                if not User.objects.filter(username=username_auto).exists():
                    if dry:
                        resumen.append(f"[DRY] Crear autoservicio {username_auto} para org {org.codigo}")
                    else:
                        user_auto = User.objects.create_user(username=username_auto, password=password)
                        user_auto.first_name = 'Autoservicio'
                        user_auto.last_name = org.nombre[:40]
                        user_auto.save()
                        UsuarioPerfilOptimizador.objects.create(user=user_auto, rol='autoservicio', organizacion=org)
                        created_count += 1
                        resumen.append(f"OK Autoservicio {username_auto}")
                else:
                    skipped_count += 1
                    resumen.append(f"Skip autoservicio {username_auto} (ya existe)")

        self.stdout.write("\nResumen creación de usuarios:")
        for r in resumen:
            self.stdout.write(f" - {r}")
        self.stdout.write(f"\nUsuarios creados: {created_count} | Omitidos: {skipped_count}")
        if dry:
            self.stdout.write("(DRY-RUN: no se creó nada)")