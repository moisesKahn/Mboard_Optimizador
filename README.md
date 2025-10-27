# Mboard Optimizador

Panel de optimización de materiales multi–organización (Django) con chat en tiempo real por polling, control de accesos por rol, gestión de materiales (tableros y tapacantos), exportación a PDF y UI moderna.

[![CI](https://github.com/moisesKahn/Mboard_Optimizador/actions/workflows/ci.yml/badge.svg)](https://github.com/moisesKahn/Mboard_Optimizador/actions/workflows/ci.yml)

## Requisitos
- Python 3.11+ (recomendado)
- Pip
- (Opcional) virtualenv

## Estructura
- `Django/` – Proyecto Django principal (carpeta que contiene `manage.py` y `WowDash/`)
- `Django/static/` – Archivos estáticos (CSS/JS/imagenes)
- `Django/templates/` – Plantillas
- `Django/core/` – App principal (modelos, migraciones, comandos de gestión)

## Puesta en marcha (Windows PowerShell)
```powershell
cd "c:\Users\Moise\Documents\Mboard\base"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt

# Preparar DB (SQLite por defecto)
cd Django
python manage.py migrate

# Crear superusuario (opcional)
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver 0.0.0.0:8000
```

## Puesta en marcha (Linux/macOS)
```bash
cd ~/Mboard/base
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

cd Django
python manage.py migrate
python manage.py createsuperuser  # opcional
python manage.py runserver 0.0.0.0:8000
```

## Funcionalidades clave
- Multi–organización con roles: super_admin, org_admin, agente, subordinador.
- Chat con conversaciones, conteo de no leídos y notificaciones sonoras (polling).
- Materiales por organización (tableros y tapacantos), importación CSV, búsqueda y paginación.
- Optimizador: exportación a PDF, gating del botón durante la generación.
- Dashboard con resumen del perfil y métricas por organización.

## Importación de materiales
Consulta `Django/static/docs/IMPORTACION_MATERIALES.md` para el formato CSV de Tableros y Tapacantos.

## Comandos de gestión útiles
Desde `Django/`:
```bash
# Replicar materiales/tapacantos a todas las organizaciones (dry-run)
python manage.py migrar_materiales_organizaciones --dry-run --exclude-general

# Ejecución real
python manage.py migrar_materiales_organizaciones
```

## Variables/Entorno
- Por defecto usa SQLite. Si deseas apuntar a PostgreSQL (por ejemplo, a la MISMA base que usa tu URL de despliegue), configura variables de entorno:

		1) Copia `Django/.env.example` a `Django/.env` (recomendado) o crea `.env` en la raíz del repo.
		2) Rellena `DATABASE_URL` con la URL exacta de tu base (formato: `postgres://user:pass@host:port/db?sslmode=require`).
		3) Ajusta `CSRF_TRUSTED_ORIGINS` para incluir el host:puerto donde correrás el servidor.
		4) Opcional: `DJANGO_ALLOWED_HOSTS=*` en desarrollo.

		WowDash/settings.py intenta cargar `.env` tanto desde `Django/.env` como desde la raíz; si existen ambos, `Django/.env` tiene prioridad.

### Ejecutar servidor en un puerto específico (usando la misma DB de la URL)

Desde `Django/`:

```bash
python manage.py migrate              # usa la DB definida en DATABASE_URL
python manage.py runserver 0.0.0.0:8000
```

Si necesitas otro puerto, cambia `8000` por el que prefieras.

## Tests / Lint
Este repo trae un pipeline simple con GitHub Actions que:
- Instala dependencias (requirements + dev)
- Ejecuta ruff (lint) y `python manage.py check`

Localmente puedes ejecutar:
```bash
pip install -r requirements-dev.txt
ruff check .
cd Django && python manage.py check
```

## Despliegue
- Ajusta `ALLOWED_HOSTS` en `WowDash/settings.py`.
- Configura `DEBUG = False` y un `SECRET_KEY` seguro en variables de entorno para producción.
- Usa un servidor WSGI (gunicorn/uwsgi) detrás de Nginx/Apache.

## Licencia
MIT – ver `LICENSE`.
