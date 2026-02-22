FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Usamos libpq5 para Postgres, pero sin compiladores.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Forzamos psycopg2-binary en el build para evitar compilación
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psycopg2-binary && \
    pip install --no-cache-dir -r requirements.txt

COPY src/ src/

RUN groupadd -g 1000 astra && \
    useradd -u 1000 -g astra -s /bin/sh -m astra && \
    chown -R astra:astra /app

USER astra
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
