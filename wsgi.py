import os
import sys
from pathlib import Path

# Añadir la carpeta 'Django' al PYTHONPATH para que el paquete WowDash sea importable desde la raíz
BASE_DIR = Path(__file__).resolve().parent
DJANGO_DIR = BASE_DIR / 'Django'
if str(DJANGO_DIR) not in sys.path:
    sys.path.insert(0, str(DJANGO_DIR))

# Configurar el módulo de settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
