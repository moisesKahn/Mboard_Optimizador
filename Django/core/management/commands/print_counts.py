from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.models import (
    Organizacion,
    Cliente,
    Material,
    Tapacanto,
    Proyecto,
    Conversacion,
    Mensaje,
    MensajeLeido,
)


class Command(BaseCommand):
    help = "Imprime conteos de datos en la base de datos por defecto (local)"

    def handle(self, *args, **options):
        User = get_user_model()
        counts = {
            "Usuarios": User.objects.count(),
            "Organizaciones": Organizacion.objects.count(),
            "Clientes": Cliente.objects.count(),
            "Materiales": Material.objects.count(),
            "Tapacantos": Tapacanto.objects.count(),
            "Proyectos": Proyecto.objects.count(),
            "Conversaciones": Conversacion.objects.count(),
            "Mensajes": Mensaje.objects.count(),
            "MensajesLeidos": MensajeLeido.objects.count(),
        }
        for label, value in counts.items():
            self.stdout.write(f"{label}: {value}")
        self.stdout.write(self.style.SUCCESS("Conteos locales listos"))
