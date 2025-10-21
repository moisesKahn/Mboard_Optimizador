import os
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Verifica conexión y muestra conteos básicos de tablas en una BD destino (Render) pasada por --target"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            dest="target_url",
            required=True,
            help="URL de la BD destino. Ej: postgresql://user:pass@host:5432/db?sslmode=require",
        )

    def handle(self, *args, **options):
        target_url = options["target_url"]
        parsed = urlparse(target_url)
        query = parse_qs(parsed.query)
        pg_options = {"sslmode": query.get("sslmode", [None])[0]} if query.get("sslmode") else {}

        # Deriva de default para heredar claves opcionales
        conf = settings.DATABASES.get("default", {}).copy()
        conf.update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path.lstrip("/"),
                "USER": parsed.username,
                "PASSWORD": parsed.password,
                "HOST": parsed.hostname,
                "PORT": str(parsed.port or ""),
            }
        )
        if pg_options:
            base_opts = conf.get("OPTIONS", {}).copy()
            base_opts.update(pg_options)
            conf["OPTIONS"] = base_opts

        settings.DATABASES["target"] = conf
        conn = connections["target"]
        self.stdout.write("Probando conexión a target...")
        conn.ensure_connection()
        self.stdout.write(self.style.SUCCESS("Conexión target OK"))

        checks = [
            ("auth_user", "Usuarios"),
            ("core_organizacion", "Organizaciones"),
            ("core_material", "Materiales"),
            ("core_tapacanto", "Tapacantos"),
            ("core_proyecto", "Proyectos"),
        ]
        with conn.cursor() as cur:
            for table, label in checks:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    self.stdout.write(f"{label}: {count}")
                except Exception as e:
                    self.stdout.write(f"{label}: (no disponible) -> {e}")

        self.stdout.write(self.style.SUCCESS("Verificación finalizada"))
