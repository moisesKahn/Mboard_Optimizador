from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Sistema Optimizador'
    
    def ready(self):
        # Importar señales para registrar auditoría de modelos
        try:
            import core.signals  # noqa: F401
        except Exception:
            # Si la importación falla en instalación/migrations, no bloquear el arranque
            pass