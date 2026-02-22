FROM python:3.11-slim

# Metadatos
LABEL maintainer="ASTRA DevOps Team"
LABEL module="astra-ingest"
LABEL description="Document Ingestion & Media Mining Service"

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Asegurar que los binarios de usuario estén en el PATH
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# [Fase2-T01] Dependencias de Sistema (FFmpeg + Build Tools)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias de Python
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip wheel setuptools && \
    pip install --prefer-binary -r requirements.txt

# [Fase2-T01] Instalación de yt-dlp (Latest)
# Se instala explícitamente vía pip para garantizar la versión más reciente
# y evitar problemas de Throttling con YouTube.
RUN pip install --no-cache-dir yt-dlp

# -----------------------------------------------------------------------------
# Código Fuente y Seguridad
# -----------------------------------------------------------------------------
COPY . .

# Crear usuario no-root para ejecución segura
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Cambiar a usuario no privilegiado
USER appuser

# Exponer puerto (Documentación)
EXPOSE 8000

# Healthcheck usando curl (instalado arriba)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicio
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]