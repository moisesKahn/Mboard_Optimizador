#!/usr/bin/env bash
set -euo pipefail

# Carga variables de entorno desde .env (raíz) y Django/.env si existen.
# Django/.env tiene prioridad.
if [ -f ".env" ]; then
  set -a; source ./.env; set +a
fi
if [ -f "Django/.env" ]; then
  set -a; source ./Django/.env; set +a
fi

PORT="${PORT:-8000}"
echo "[dev] Usando puerto $PORT"

# Ir a la carpeta Django
cd "$(dirname "$0")/../Django"

# Migraciones (idempotentes)
/bin/python3 manage.py migrate

# Iniciar servidor
exec /bin/python3 manage.py runserver 0.0.0.0:"${PORT}"