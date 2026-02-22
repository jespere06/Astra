#!/bin/bash
# Ejecutar desde la raíz del módulo: ./scripts/generate_protos.sh

echo "Generando código gRPC..."
python3 -m grpc_tools.protoc \
    -I src/protos \
    --python_out=src/generated \
    --grpc_python_out=src/generated \
    src/protos/asset.proto

# Fix temporal para imports relativos en Python 3 (problema conocido de protoc)
# Usando g-sed o sed compatible con macOS
sed -i '' 's/import asset_pb2 as asset__pb2/from . import asset_pb2 as asset__pb2/g' src/generated/asset_pb2_grpc.py

echo "Generación completada en src/generated/"
