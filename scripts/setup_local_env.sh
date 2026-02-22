#!/bin/bash
# scripts/setup_local_env.sh

set -e

echo "🐍 Creando entorno virtual unificado para ASTRA..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ venv creado."
else
    echo "ℹ️ venv ya existe, saltando creación."
fi

source venv/bin/activate

echo "📦 Instalando dependencias base y herramientas de desarrollo..."
pip install --upgrade pip wheel setuptools
pip install pytest httpx uvicorn pydantic-settings boto3 psycopg2-binary

echo "📦 Instalando dependencias de todos los servicios..."

# Shared Kernel
if [ -f "libs/shared-kernel/requirements.txt" ]; then
    echo "🔹 libs/shared-kernel..."
    pip install -r libs/shared-kernel/requirements.txt
fi

# Orchestrator
if [ -f "services/astra-orchestrator/requirements.txt" ]; then
    echo "🔹 astra-orchestrator..."
    pip install -r services/astra-orchestrator/requirements.txt
fi

# Core
if [ -f "services/astra-core/requirements.txt" ]; then
    echo "🔹 astra-core..."
    pip install -r services/astra-core/requirements.txt
fi

# Ingest
if [ -f "modules/astra-ingest/requirements.txt" ]; then
    echo "🔹 astra-ingest..."
    pip install -r modules/astra-ingest/requirements.txt
fi

# Builder
if [ -f "services/astra-builder/requirements.txt" ]; then
    echo "🔹 astra-builder..."
    pip install -r services/astra-builder/requirements.txt
fi

# Guard
if [ -f "services/astra-guard/requirements.txt" ]; then
    echo "🔹 astra-guard..."
    pip install -r services/astra-guard/requirements.txt
fi

# Learn
if [ -f "services/astra-learn/requirements.txt" ]; then
    echo "🔹 astra-learn..."
    pip install -r services/astra-learn/requirements.txt
fi

# Tenant Config
if [ -f "services/tenant-config-service/requirements.txt" ]; then
    echo "🔹 tenant-config-service..."
    pip install -r services/tenant-config-service/requirements.txt
fi

echo "✅ Entorno Python listo! 🎉"
echo "👉 Usa 'source venv/bin/activate' antes de correr servicios manualmente."
