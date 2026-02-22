import logging
import traceback
import os
from uuid import UUID
from typing import List
from src.db.base import SessionLocal
from src.db.models import IngestJob, JobStatus
from src.core.ingest_orchestrator import IngestOrchestrator

logger = logging.getLogger(__name__)

def process_ingest_job(job_id: UUID, file_paths: List[str]):
    """
    Función wrapper que se ejecuta en el Worker (Background Task).
    Maneja la transacción de estado del Job y llama al núcleo lógico.
    """
    db = SessionLocal()
    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    
    if not job:
        logger.error(f"Job {job_id} no encontrado en DB al iniciar worker.")
        return

    try:
        # 1. Actualizar estado a PROCESSING
        logger.info(f"🚀 Iniciando Job {job_id}...")
        job.status = JobStatus.PROCESSING
        db.commit()

        # 2. Instanciar Orquestador
        # Nota: El orquestador maneja su propia sesión de DB interna para operaciones granulares,
        # pero aquí usamos una sesión externa para controlar el estado del Job.
        orchestrator = IngestOrchestrator(db)

        # 3. Ejecutar Pipeline Core
        # Validar existencia de archivos (Simulación de descarga S3)
        valid_files = [f for f in file_paths if os.path.exists(f)]
        
        if not valid_files:
            raise FileNotFoundError(f"Ninguno de los archivos proporcionados existe localmente. Rutas recibidas: {file_paths}")

        # Ejecución
        result_summary = orchestrator.process_batch(valid_files, tenant_id=job.tenant_id)

        # 4. Finalización Exitosa
        job.status = JobStatus.COMPLETED
        job.error_log = result_summary # Guardamos el resumen como log positivo
        db.commit()
        logger.info(f"✅ Job {job_id} completado: {result_summary}")

    except Exception as e:
        # 5. Manejo de Fallos
        error_msg = f"Error crítico en Job {job_id}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        
        job.status = JobStatus.FAILED
        job.error_log = error_msg
        db.commit()
    
    finally:
        db.close()