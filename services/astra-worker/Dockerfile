# Usamos imagen base de NVIDIA con CUDA 11.8 (Compatible con PyTorch 2.x y Faster-Whisper)
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Configuración de entorno para evitar interacciones durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
# PYTHONPATH incluye el directorio actual y el kernel compartido
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/libs/shared-kernel"

WORKDIR /app

# 1. Instalación de dependencias de sistema
# python3.10, pip, ffmpeg (crítico para audio), git
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear alias para python
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# 2. Instalación de librerías Python pesadas (Capa de Caché)
# Instalamos Torch y Faster-Whisper primero para que Docker cachee esta capa
# ya que son las que más tardan y cambian menos frecuentemente que el código.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && \
    pip install --no-cache-dir faster-whisper runpod

# 3. Instalación de requerimientos específicos del servicio
COPY services/astra-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia del Kernel Compartido (Debe ejecutarse desde la raíz del repo)
COPY libs/shared-kernel/ ./libs/shared-kernel/

# 5. Copia del Código Fuente del Worker
COPY services/astra-worker/src/ ./src/

# 6. Entrypoint para RunPod Serverless
# Usamos -u para output sin buffer (logs en tiempo real)
CMD [ "python", "-u", "-m", "src.worker" ]
