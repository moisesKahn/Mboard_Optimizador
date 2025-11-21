import os, sys, secrets, string
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Django/
# Ensure project path in sys.path
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
import django
django.setup()
from django.contrib.auth.models import User
from core.models import Organizacion, UsuarioPerfilOptimizador

USERNAME = 'autoservicio_demo'
# Generate strong password: 12 chars letters+digits+symbols
alphabet = string.ascii_letters + string.digits + '!@$%*_-'
password = 'Auto$' + ''.join(secrets.choice(alphabet) for _ in range(8))

org = Organizacion.objects.filter(activo=True).order_by('id').first()
if not org:
    print('ERROR: No hay organización activa para asignar.')
    sys.exit(1)

user = User.objects.filter(username=USERNAME).first()
if not user:
    user = User.objects.create_user(username=USERNAME, password=password)
    user.first_name = 'Autoservicio'
    user.last_name = org.nombre[:40]
    user.save()
    UsuarioPerfilOptimizador.objects.create(user=user, rol='autoservicio', organizacion=org)
    accion = 'CREADO'
else:
    user.set_password(password)
    user.save()
    # Ensure profile exists
    if not hasattr(user, 'usuarioperfiloptimizador'):
        UsuarioPerfilOptimizador.objects.create(user=user, rol='autoservicio', organizacion=org)
    accion = 'ACTUALIZADO'

print(f"ACCION={accion}")
print(f"USERNAME={user.username}")
print(f"PASSWORD={password}")
print(f"ORGANIZACION={org.codigo} - {org.nombre}")
