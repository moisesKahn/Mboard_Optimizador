from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from core.models import UsuarioPerfilOptimizador, Organizacion


class Command(BaseCommand):
    help = "Crea o actualiza el superusuario ADMIN_ADMIN y su perfil super_admin en ORGANIZACION_GENERAL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            dest="password",
            default="Adm1n_!2025_temp",
            help="Contraseña a asignar al usuario ADMIN_ADMIN (por defecto: Adm1n_!2025_temp)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options.get("password") or "Adm1n_!2025_temp"

        # Organización general
        org, _ = Organizacion.objects.get_or_create(
            nombre="ORGANIZACION_GENERAL",
            defaults={"is_general": True},
        )
        if getattr(org, "is_general", None) is not True:
            org.is_general = True
            org.save(update_fields=["is_general"]) 

        # Usuario
        user, created = User.objects.get_or_create(
            username="ADMIN_ADMIN",
            defaults={
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "Admin",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        # Asegurar flags de superusuario/activo
        changed_flags = False
        for attr, val in ("is_active", True), ("is_staff", True), ("is_superuser", True):
            if getattr(user, attr) is not True:
                setattr(user, attr, True)
                changed_flags = True
        # Asignar contraseña
        user.set_password(password)
        user.save()

        # Perfil extendido
        perfil, _ = UsuarioPerfilOptimizador.objects.get_or_create(
            user=user,
            defaults={"rol": "super_admin", "organizacion": org, "activo": True},
        )
        updates = []
        if getattr(perfil, "rol", None) != "super_admin":
            perfil.rol = "super_admin"; updates.append("rol")
        if getattr(perfil, "organizacion_id", None) != org.id:
            perfil.organizacion = org; updates.append("organizacion")
        if getattr(perfil, "activo", None) is not True:
            perfil.activo = True; updates.append("activo")
        # Si el modelo tiene must_change_password, activarlo para forzar cambio al ingresar
        if hasattr(perfil, "must_change_password") and getattr(perfil, "must_change_password") is not True:
            perfil.must_change_password = True; updates.append("must_change_password")
        if updates:
            perfil.save()

        self.stdout.write(self.style.SUCCESS(
            f"OK - Usuario ADMIN_ADMIN {'creado' if created else 'actualizado'} con contraseña establecida y rol super_admin."
        ))
