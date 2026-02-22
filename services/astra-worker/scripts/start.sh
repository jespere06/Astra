#!/bin/bash
set -euo pipefail

echo "╔══════════════════════════════════════════╗"
echo "║   ASTRA-WORKER — GPU Transcription Job   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Provider : ${TRANSCRIPTION_PROVIDER:-whisper}"
echo "Model    : ${WHISPER_MODEL_SIZE:-large-v3-turbo}"
echo "Job ID   : ${JOB_ID:-N/A}"
echo ""

# Verificar GPU
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU ONLY\"}')" 2>/dev/null || echo "GPU: Not available"
echo ""

# Ejecutar Worker
exec python -m src.worker
