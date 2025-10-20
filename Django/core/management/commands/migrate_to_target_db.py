import io
import os
import sys
import tempfile
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.db import connections


class Command(BaseCommand):
    help = (
        "Migra datos desde la BD 'default' a una BD 'target' usando dumpdata/loaddata. "
        "La BD 'target' se toma de --target o de la variable TARGET_DATABASE_URL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            dest="target_url",
            default=None,
            help=(
                "URL de la BD destino. Si no se especifica, se usa la variable TARGET_DATABASE_URL. "
                "Ej: postgresql://user:pass@host:5432/dbname?sslmode=require"
            ),
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[
                "contenttypes",
                "auth.permission",
                "admin.LogEntry",
                "sessions.session",
            ],
            help="Apps o modelos a excluir en dumpdata (puede repetirse).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo valida conexión y genera dump temporal sin cargar en target.",
        )
        parser.add_argument(
            "--skip-load",
            action="store_true",
            help="No realiza dump/loaddata; solo aplica migraciones y ajusta secuencias en target.",
        )

    def handle(self, *args, **options):
        target_url = options.get("target_url") or os.getenv("TARGET_DATABASE_URL")
        if not target_url:
            self.stderr.write(
                self.style.ERROR(
                    "Falta TARGET_DATABASE_URL o --target. Ejemplo:\n"
                    "--target postgresql://user:pass@host:5432/dbname?sslmode=require"
                )
            )
            sys.exit(1)

        # Configurar conexión 'target' dinámicamente
        parsed = urlparse(target_url)
        if parsed.scheme not in ("postgres", "postgresql"):
            self.stderr.write(self.style.ERROR("La URL debe empezar con postgres:// o postgresql://"))
            sys.exit(1)

        # Extrae opciones de la query (p.ej., sslmode)
        query = parse_qs(parsed.query)
        pg_options = {}
        if "sslmode" in query:
            pg_options["sslmode"] = query["sslmode"][0]

        # Partimos de la config por defecto para heredar claves esperadas (TIME_ZONE, AUTOCOMMIT, etc.)
        target_conf = settings.DATABASES.get("default", {}).copy()
        target_conf.update({
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": str(parsed.port or ""),
        })
        # Asegurar claves esperadas
        target_conf.setdefault("CONN_MAX_AGE", settings.DATABASES.get("default", {}).get("CONN_MAX_AGE", 0))
        target_conf.setdefault("TIME_ZONE", None)
        # Merge OPTIONS
        base_options = target_conf.get("OPTIONS", {}).copy()
        if pg_options:
            base_options.update(pg_options)
        if base_options:
            target_conf["OPTIONS"] = base_options

        # Inyectar alias 'target' y probar conexión
        settings.DATABASES["target"] = target_conf
        conn = connections["target"]
        self.stdout.write("Conectando a base de datos target...")
        conn.ensure_connection()
        self.stdout.write(self.style.SUCCESS("Conexión OK"))

        # Asegurar esquema en target
        self.stdout.write("Aplicando migraciones en target...")
        call_command("migrate", database="target", interactive=False, verbosity=1)
        self.stdout.write(self.style.SUCCESS("Migraciones aplicadas en target"))

        if not options["skip_load"]:
            # Generar dump desde default
            excludes = options["exclude"]
            self.stdout.write(f"Excluyendo: {', '.join(excludes)}")
            buf = io.StringIO()
            call_command(
                "dumpdata",
                natural_foreign=True,
                natural_primary=True,
                exclude=excludes,
                stdout=buf,
                indent=2,
            )
            data = buf.getvalue()
            if not data.strip().startswith("["):
                self.stderr.write(self.style.ERROR("Dump inesperado o vacío."))
                sys.exit(1)

            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            self.stdout.write(f"Dump temporal: {tmp_path}")

            if options["dry_run"]:
                self.stdout.write(self.style.WARNING("DRY-RUN: no se cargarán datos en target."))
                return

            # Cargar en target
            self.stdout.write("Cargando datos en target (loaddata)...")
            call_command("loaddata", tmp_path, database="target", verbosity=1)
            self.stdout.write(self.style.SUCCESS("Datos cargados en target"))

        # Reset de secuencias para apps relevantes
        self.stdout.write("Reiniciando secuencias en target...")
        from django.apps import apps as django_apps
        app_labels = [app.label for app in django_apps.get_app_configs()]
        sql_buf = io.StringIO()
        call_command("sqlsequencereset", *app_labels, database="target", stdout=sql_buf)
        sql = sql_buf.getvalue()
        if "setval(" not in sql:
            self.stdout.write("No hay secuencias que ajustar.")
        else:
            try:
                with connections["target"].cursor() as cursor:
                    cursor.execute(sql)
                self.stdout.write(self.style.SUCCESS("Secuencias ajustadas en target"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"No se pudo ajustar secuencias: {e}"))
        self.stdout.write(self.style.SUCCESS("Migración de datos COMPLETADA"))
