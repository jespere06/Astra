#!/bin/bash

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 ASTRA SMOKE TEST RUNNER${NC}"
echo "========================================"

# 1. Setup Virtualenv (Opcional, asumiendo entorno contenedor o local limpio)
# python3 -m venv venv
# source venv/bin/activate

# 2. Instalar dependencias
echo "📦 Installing test dependencies..."
pip install -r requirements.txt -q

# 3. Esperar servicios (Simple sleep o usar wait-for-it en docker)
# echo "⏳ Waiting for services..."
# sleep 5

# 4. Ejecutar Pytest
# -v: Verbose
# --junitxml: Generar reporte para CI/CD
# -s: Mostrar print() en consola
echo "🔥 Running Tests..."
pytest -v -s --junitxml=report.xml

EXIT_CODE=$?

echo "========================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ SMOKE TEST PASSED${NC}"
else
    echo -e "${RED}❌ SMOKE TEST FAILED${NC}"
fi

exit $EXIT_CODE
