#!/usr/bin/env python3
"""
ASTRA Mining CLI - Pipeline de Generación de Datasets (Fase 2)

Uso:
    python src/scripts/run_mining.py --csv inputs.csv --output ./data --tenant concejo_demo
"""
import sys
import os
import argparse
import logging

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.pipeline import MiningOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def main():
    parser = argparse.ArgumentParser(description="Ejecuta el pipeline de minería de datos ASTRA.")
    
    parser.add_argument("--csv", required=True, help="Ruta al archivo CSV con las fuentes (video_url, docx_path).")
    parser.add_argument("--output", required=True, help="Directorio donde se guardarán los datasets (.jsonl).")
    parser.add_argument("--tenant", default="default", help="ID del Tenant para organización en S3.")
    parser.add_argument("--provider", default="deepgram", choices=["deepgram", "whisper"], help="Motor de transcripción a usar.")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta validaciones sin descargar ni transcribir.")
    
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ Error: El archivo CSV '{args.csv}' no existe.")
        sys.exit(1)

    orchestrator = MiningOrchestrator(
        output_dir=args.output,
        tenant_id=args.tenant
    )

    try:
        report = orchestrator.process_batch(
            csv_path=args.csv,
            provider=args.provider,
            dry_run=args.dry_run
        )
        
        print("\n" + "="*40)
        print("🏁 Ejecución Finalizada")
        print("="*40)
        print(f"Total Procesado: {report['total_rows']}")
        print(f"Éxitos:          {report['success']}")
        print(f"Fallos:          {report['failed']}")
        
        if 'dataset_stats' in report:
            stats = report['dataset_stats']
            print(f"Dataset Train:   {stats.get('train', 0)} ejemplos")
            print(f"Dataset Val:     {stats.get('val', 0)} ejemplos")
            
    except Exception as e:
        print(f"❌ Error crítico en el pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
