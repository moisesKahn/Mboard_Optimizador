from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from core.models import UsuarioPerfilOptimizador, Organizacion


class Command(BaseCommand):
    help = (
        "Crea o actualiza un superusuario con perfil super_admin y lo asigna a ORGANIZACION_GENERAL. "
        "Uso: manage.py ensure_superuser --username USER --email MAIL --password PASS"
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Nombre de usuario a crear/actualizar")
        parser.add_argument("--email", required=False, default="", help="Email del usuario")
        parser.add_argument("--password", required=True, help="Contraseña a asignar")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        email = (options.get("email") or "").strip()
        password = options["password"]

        if not username:
            self.stderr.write(self.style.ERROR("--username es obligatorio"))
            return

        # Asegurar organización GENERAL
        org, _ = Organizacion.objects.get_or_create(
            nombre="ORGANIZACION_GENERAL",
            defaults={"is_general": True},
        )
        if getattr(org, "is_general", None) is not True:
            org.is_general = True
            org.save(update_fields=["is_general"]) 

        # Usuario
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email or f"{username.lower()}@example.com",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        # Asegurar flags
        changed = False
        for attr in ("is_active", "is_staff", "is_superuser"):
            if getattr(user, attr) is not True:
                setattr(user, attr, True)
                changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        # Asignar contraseña
        user.set_password(password)
        user.save()

        # Perfil
        perfil, _ = UsuarioPerfilOptimizador.objects.get_or_create(
            user=user,
            defaults={"rol": "super_admin", "organizacion": org, "activo": True},
        )
        to_update = False
        if getattr(perfil, "rol", None) != "super_admin":
            perfil.rol = "super_admin"; to_update = True
        if getattr(perfil, "organizacion_id", None) != org.id:
            perfil.organizacion = org; to_update = True
        if getattr(perfil, "activo", None) is not True:
            perfil.activo = True; to_update = True
        if hasattr(perfil, "must_change_password") and getattr(perfil, "must_change_password", None) is not True:
            perfil.must_change_password = True; to_update = True
        if to_update:
            perfil.save()

        self.stdout.write(self.style.SUCCESS(
            f"OK - Usuario {username} {'creado' if created else 'actualizado'} como superusuario y perfil super_admin."
        ))
