from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Establece la contraseña de un usuario por username (no interactivo).'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Nombre de usuario')
        parser.add_argument('--password', required=True, help='Nueva contraseña en texto claro')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"El usuario '{username}' no existe")
        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write(self.style.SUCCESS(f"Contraseña actualizada para '{username}'"))
