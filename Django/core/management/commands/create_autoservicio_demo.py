import secrets
import string
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Organizacion, UsuarioPerfilOptimizador

class Command(BaseCommand):
    help = "Crear/actualizar usuario autoservicio_demo y mostrar credenciales generadas"

    def add_arguments(self, parser):
        parser.add_argument('--password-length', type=int, default=12, help='Longitud de la parte aleatoria de la contraseña')
        parser.add_argument('--username', default='autoservicio_demo', help='Username a crear/actualizar')
        parser.add_argument('--org-codigo', default=None, help='Código de organización específico; si se omite usa la primera activa')
        parser.add_argument('--set-password', default=None, help='Fijar esta contraseña en lugar de generar una aleatoria')

    def handle(self, *args, **options):
        username = options['username']
        plen = options['password_length']
        org_codigo = options['org_codigo']

        # Selección de organización
        org = None
        if org_codigo:
            org = Organizacion.objects.filter(codigo__iexact=org_codigo, activo=True).first()
            if not org:
                self.stderr.write(self.style.ERROR(f"Organización con código '{org_codigo}' no encontrada o inactiva"))
                return
        else:
            org = Organizacion.objects.filter(activo=True).order_by('id').first()
        if not org:
            self.stderr.write(self.style.ERROR("No hay organizaciones activas"))
            return

        # Generar contraseña segura
        if options['set_password']:
            password = options['set_password']
        else:
            alphabet = string.ascii_letters + string.digits + '!@$%*_-'
            random_part = ''.join(secrets.choice(alphabet) for _ in range(plen))
            password = 'Auto$' + random_part

        user = User.objects.filter(username=username).first()
        accion = 'ACTUALIZADO'
        if not user:
            user = User.objects.create_user(username=username, password=password)
            accion = 'CREADO'
        else:
            user.set_password(password)
        user.first_name = 'Autoservicio'
        user.last_name = org.nombre[:40]
        user.save()

        # Perfil
        if not hasattr(user, 'usuarioperfiloptimizador'):
            UsuarioPerfilOptimizador.objects.create(user=user, rol='autoservicio', organizacion=org)
        else:
            perfil = user.usuarioperfiloptimizador
            if perfil.rol != 'autoservicio' or perfil.organizacion_id != org.id:
                perfil.rol = 'autoservicio'
                perfil.organizacion = org
                perfil.save(update_fields=['rol', 'organizacion'])

        self.stdout.write(self.style.SUCCESS(f"ACCION={accion}"))
        self.stdout.write(f"USERNAME={user.username}")
        self.stdout.write(f"PASSWORD={password}")
        self.stdout.write(f"ORGANIZACION={org.codigo} - {org.nombre}")