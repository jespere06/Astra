#!/bin/bash
# ASTRA Optimized Build Script (Local Mac M1/M2/M3)
# Este script implementa las mejores prácticas para evitar lentitud en Mac.

export DOCKER_BUILDKIT=1
export DOCKER_DEFAULT_PLATFORM=linux/arm64

echo "🚀 Iniciando construcción optimizada para ASTRA..."

# Limpiar caché si se solicita
if [ "$1" == "--clean" ]; then
    echo "🧹 Limpiando caché de construcción..."
    docker builder prune -f
fi

# Construir servicios ligeros
echo "📦 Construyendo servicios con flags de velocidad (No provenance/attestations)..."
docker buildx build --platform linux/arm64 --provenance=false --attest=type=sbom,disabled=true --attest=type=provenance,disabled=true \
    -t astra-orchestrator ./services/astra-orchestrator --load

docker buildx build --platform linux/arm64 --provenance=false --attest=type=sbom,disabled=true --attest=type=provenance,disabled=true \
    -t astra-core ./services/astra-core --load

docker buildx build --platform linux/arm64 --provenance=false --attest=type=sbom,disabled=true --attest=type=provenance,disabled=true \
    -t astra-ingest ./modules/astra-ingest --load

# Levantar el resto de la infraestructura
echo "🏗️ Levantando el stack completo..."
docker compose up -d

echo "✅ ASTRA está listo y corriendo!"
