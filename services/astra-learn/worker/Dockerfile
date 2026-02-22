# Usar imagen base optimizada de Unsloth (CUDA 12.1, PyTorch 2.2)
FROM unslothai/unsloth:latest-cu121-torch230

WORKDIR /app

# Instalar dependencias del sistema mínimas
# Unsloth ya trae casi todo, solo añadimos lo específico de nuestro worker
RUN apt-get update && apt-get install -y --no-install-recommends \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Instalar librerías de Python para manejo de I/O y Serverless
RUN pip install --no-cache-dir \
    runpod \
    requests \
    scipy \
    boto3

# Copiar el código fuente
# Estructura: raíz del contexto -> /app
COPY services/astra-learn/runpod_training_handler.py /app/runpod_training_handler.py
COPY services/astra-learn/src /app/src

# Configuración de entorno
ENV PYTHONPATH=/app
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Comando de inicio
CMD [ "python", "-u", "/app/runpod_training_handler.py" ]