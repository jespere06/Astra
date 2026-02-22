FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# SOLO instalamos curl para healthcheck. ADIÓS build-essential.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
RUN chmod +x scripts/start.sh

EXPOSE 8000

# Usuario no-root para seguridad
RUN groupadd -g 1000 astra && \
    useradd -u 1000 -g astra -s /bin/sh -m astra && \
    chown -R astra:astra /app

USER astra

CMD ["./scripts/start.sh"]
