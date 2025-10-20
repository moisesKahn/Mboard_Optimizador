from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import UsuarioPerfilOptimizador, Organizacion


class Command(BaseCommand):
    help = "Garantiza que un usuario tenga rol super_admin y pertenezca a la Organización General"

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Nombre de usuario a configurar')
        parser.add_argument('--org-name', default='ORGANIZACION_GENERAL', help='Nombre de la organización general')
        parser.add_argument('--must-change', action='store_true', default=False, help='Marcar que debe cambiar la contraseña')

    def handle(self, *args, **options):
        username = options['username']
        org_name = options['org-name']
        must_change = options['must_change']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Usuario '{username}' no existe. Crea primero el superusuario.")

        # Asegurar flags de admin Django
        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if changed:
            user.save(update_fields=['is_staff', 'is_superuser'])

        # Asegurar organización general
        org = Organizacion.objects.filter(is_general=True).first()
        if not org:
            org, _ = Organizacion.objects.get_or_create(nombre=org_name, defaults={'is_general': True})
            if not org.is_general:
                org.is_general = True
                org.save(update_fields=['is_general'])

        # Asegurar perfil con rol super_admin
        perfil, created = UsuarioPerfilOptimizador.objects.get_or_create(
            user=user,
            defaults={'rol': 'super_admin', 'organizacion': org, 'activo': True, 'must_change_password': must_change}
        )
        if not created:
            updated = False
            if perfil.rol != 'super_admin':
                perfil.rol = 'super_admin'
                updated = True
            if perfil.organizacion_id != org.id:
                perfil.organizacion = org
                updated = True
            if must_change and not perfil.must_change_password:
                perfil.must_change_password = True
                updated = True
            if not perfil.activo:
                perfil.activo = True
                updated = True
            if updated:
                perfil.save()

        self.stdout.write(self.style.SUCCESS(f"Usuario '{username}' asegurado como super_admin en Organización General."))
