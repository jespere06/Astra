
import os
import time
import json
import random
import glob
import logging
from typing import List
from sqlalchemy.orm import Session
from src.db.base import SessionLocal
from src.db.models import Template, Skeleton, LabelCatalog, IngestJob, StyleMap, ZoneMapping
from src.core.ingest_orchestrator import IngestOrchestrator
from tests.benchmark.monitor import ResourceMonitor

# Configuración
TENANT_ID = "benchmark_test"
DOCS_DIR = "/Users/jesusandresmezacontreras/projects/astra/minutes"
SCENARIOS = [5, 25, 50]
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results_raw.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Benchmark")

def cleanup_db(db: Session):
    """Limpia los datos del tenant de benchmark para evitar contaminación."""
    logger.info(f"🧹 Limpiando DB para tenant {TENANT_ID}...")
    
    # 1. Obtener IDs de plantillas del tenant
    template_ids = [t[0] for t in db.query(Template.id).filter(Template.tenant_id == TENANT_ID).all()]
    
    # 2. Eliminar ZoneMappings que referencian esas plantillas
    if template_ids:
        db.query(ZoneMapping).filter(ZoneMapping.template_id.in_(template_ids)).delete(synchronize_session=False)
    
    # 3. Eliminar el resto de datos del tenant
    db.query(Skeleton).filter(Skeleton.tenant_id == TENANT_ID).delete()
    db.query(Template).filter(Template.tenant_id == TENANT_ID).delete()
    db.query(StyleMap).filter(StyleMap.tenant_id == TENANT_ID).delete()
    db.commit()

def run_scenarios():
    all_docs = glob.glob(os.path.join(DOCS_DIR, "*.docx"))
    if len(all_docs) < max(SCENARIOS):
        logger.warning(f"⚠️ Solo se encontraron {len(all_docs)} documentos. Ajustando escenarios.")
        scenarios = [s for s in SCENARIOS if s <= len(all_docs)]
    else:
        scenarios = SCENARIOS

    results = []
    
    for n in scenarios:
        logger.info(f"🚀 Iniciando Escenario: {n} documentos")
        db = SessionLocal()
        cleanup_db(db)
        
        # Selección aleatoria de docs
        test_docs = random.sample(all_docs, n)
        
        # Monitorización
        monitor = ResourceMonitor(interval=0.2)
        monitor.start()
        
        orchestrator = IngestOrchestrator(db)
        
        start_time = time.perf_counter()
        success = True
        try:
            # En el benchmark llamamos al proceso de batch
            summary = orchestrator.process_batch(test_docs, TENANT_ID)
            logger.info(f"✅ Summary: {summary}")
        except Exception as e:
            logger.error(f"❌ Error en batch {n}: {e}")
            success = False
        
        duration = time.perf_counter() - start_time
        metrics = monitor.stop()
        
        results.append({
            "n_docs": n,
            "duration_seconds": duration,
            "peak_ram_mb": metrics["peak_ram_mb"],
            "peak_cpu_percent": metrics["peak_cpu_percent"],
            "success": success
        })
        
        logger.info(f"⏱️ Escenario {n} completado en {duration:.2f}s (RAM Pico: {metrics['peak_ram_mb']}MB)")
        db.close()
        
    # Guardar resultados
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=4)
    logger.info(f"💾 Resultados guardados en {RESULTS_FILE}")

if __name__ == "__main__":
    run_scenarios()
