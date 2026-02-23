FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias de sistema mínimas
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar requerimientos del servicio (FastAPI, SQLAlchemy, etc.)
COPY services/astra-learn/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip wheel setuptools && \
    pip install --prefer-binary -r requirements.txt

# Copiar código fuente
COPY services/astra-learn/src/ src/

# Usuario seguro
RUN groupadd -g 1000 astra && \
    useradd -u 1000 -g astra -s /bin/sh -m astra && \
    chown -R astra:astra /app

USER astra

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]