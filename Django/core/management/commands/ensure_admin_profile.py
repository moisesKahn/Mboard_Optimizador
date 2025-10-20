from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from core.models import UsuarioPerfilOptimizador, Organizacion


class Command(BaseCommand):
    help = "Crea o actualiza un usuario admin y su perfil asociado a la ORGANIZACION_GENERAL"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="Admin_Moises", help="Nombre de usuario")
        parser.add_argument("--email", default="admin_moises@example.com", help="Email del usuario")
        parser.add_argument("--password", default=None, help="Contraseña a asignar (opcional)")
        parser.add_argument(
            "--org-nombre",
            dest="org_nombre",
            default="ORGANIZACION_GENERAL",
            help="Nombre de la organización general",
        )
        parser.add_argument(
            "--org-codigo",
            dest="org_codigo",
            default="ORG_GENERAL",
            help="Código de la organización general",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        email = options["email"]
        password = options["password"]
        org_nombre = options["org_nombre"]
        org_codigo = options["org_codigo"]

        # 1) Organización general
        org = (
            Organizacion.objects.filter(is_general=True).first()
            or Organizacion.objects.filter(codigo=org_codigo).first()
            or Organizacion.objects.filter(nombre=org_nombre).first()
        )
        if not org:
            org = Organizacion.objects.create(
                codigo=org_codigo, nombre=org_nombre, is_general=True, activo=True
            )
            self.stdout.write(self.style.SUCCESS(f"Creada organización general: {org}"))
        else:
            if not org.is_general:
                org.is_general = True
            if org.nombre != org_nombre:
                org.nombre = org_nombre
            if not org.activo:
                org.activo = True
            org.save()
            self.stdout.write(f"Usando organización general existente: {org}")

        # 2) Usuario
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        if created:
            self.stdout.write(self.style.SUCCESS(f"Usuario creado: {username}"))
        else:
            if user.email != email:
                user.email = email
        user.is_staff = True
        user.is_superuser = True
        if password:
            user.set_password(password)
        elif not user.has_usable_password():
            user.set_password("ChangeMe123!")
        user.save()

        # 3) Perfil
        perfil, _ = UsuarioPerfilOptimizador.objects.get_or_create(
            user=user,
            defaults={
                "rol": "super_admin",
                "organizacion": org,
                "activo": True,
                "must_change_password": False,
            },
        )
        perfil.rol = "super_admin"
        perfil.organizacion = org
        perfil.activo = True
        perfil.must_change_password = False
        perfil.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: usuario/perfil asegurado. username={username}, org={org_codigo}"
            )
        )
