#!/bin/bash
set -e

# Configuración de Gunicorn
# Ajustado para inferencia CPU-bound (Workers limitados para evitar thrashing)
WORKERS=${GUNICORN_WORKERS:-2}
TIMEOUT=${GUNICORN_TIMEOUT:-120}
LOG_LEVEL=${LOG_LEVEL:-info}

echo "🚀 Iniciando ASTRA-CORE con $WORKERS workers (Gunicorn/Uvicorn)..."

# Pre-compilar código Python para arranque más rápido (opcional pero recomendado)
python -m compileall src/

# Ejecutar servidor
exec gunicorn src.main:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout $TIMEOUT \
    --log-level $LOG_LEVEL \
    --access-logfile - \
    --error-logfile -
