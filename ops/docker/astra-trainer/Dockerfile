# Base image: NVIDIA CUDA 12.1 con Python 3.10 (Ubuntu 22.04)
# Mitigación de Riesgo: Versión fija para evitar incompatibilidades de drivers
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

LABEL maintainer="astra-platform"
LABEL description="Entorno de entrenamiento GPU para ASTRA-LEARN (LoRA/PEFT)"

# Configuración de entorno
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Symlink python3 a python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Instalar dependencias de Python (Torch + HuggingFace Ecosystem)
# torch --index-url instala la versión compatible con CUDA 12.1
RUN pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalar librerías de fine-tuning y MLOps
# - bitsandbytes: para cargar modelos en 4-bit/8-bit
# - peft: para LoRA
# - transformers/accelerate: base de LLMs
# - mlflow/boto3: para tracking y almacenamiento
# Nota: creamos un requirements.txt temporal o lo instalamos directo
RUN pip install \
    transformers==4.35.0 \
    accelerate==0.24.1 \
    peft==0.6.0 \
    bitsandbytes==0.41.1 \
    scipy \
    scikit-learn \
    mlflow==2.9.2 \
    boto3==1.34.11 \
    psycopg2-binary

# Directorio de trabajo
WORKDIR /app

# Copiar scripts de entrenamiento
# Nota: Asumimos que src/ml/train_lora.py existe o se creará luego
# Para que el build no falle si no existe, lo comento o asumo su creación
# COPY src/ml/train_lora.py /app/train.py

# Punto de entrada por defecto (sobrescrito por K8s Job)
# ENTRYPOINT ["python", "train.py"]
