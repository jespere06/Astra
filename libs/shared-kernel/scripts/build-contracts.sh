#!/bin/bash

# Salir si hay errores
set -e

# Directorios
PROTO_DIR="./proto"
OUT_DIR="./generated"
PY_OUT="$OUT_DIR/python"
TS_OUT="$OUT_DIR/typescript"

echo "🚀 Iniciando ASTRA Shared Kernel Build..."

# 1. Limpieza
echo "🧹 Limpiando directorios generados..."
rm -rf $OUT_DIR
mkdir -p $PY_OUT
mkdir -p $TS_OUT

# 2. Generación Python (con Type Hints .pyi)
echo "🐍 Generando contratos Python..."
# Nota: Requiere 'grpcio-tools' y 'mypy-protobuf' instalados
python3 -m grpc_tools.protoc \
    -I$PROTO_DIR \
    --python_out=$PY_OUT \
    --grpc_python_out=$PY_OUT \
    --mypy_out=$PY_OUT \
    $PROTO_DIR/*.proto

# Crear __init__.py para que sea un paquete importable
touch $PY_OUT/__init__.py
echo "from .astra_models_pb2 import *" > $PY_OUT/__init__.py

# 3. Generación TypeScript
echo "📘 Generando contratos TypeScript..."
# Nota: Requiere 'ts-proto' instalado via npm
# Opciones: 
# - esModuleInterop: compatibilidad módulos
# - outputEncodeMethods: para serializar a binario si es necesario
# - outputJsonMethods: para convertir a JSON fácilmente
protoc \
    --plugin=./node_modules/.bin/protoc-gen-ts_proto \
    --ts_proto_out=$TS_OUT \
    --ts_proto_opt=esModuleInterop=true \
    --ts_proto_opt=outputEncodeMethods=true \
    --ts_proto_opt=outputJsonMethods=true \
    --ts_proto_opt=outputClientImpl=grpc-web \
    -I$PROTO_DIR \
    $PROTO_DIR/*.proto

echo "✅ Build completado exitosamente."
echo "   📍 Python: $PY_OUT"
echo "   📍 TypeScript: $TS_OUT"
