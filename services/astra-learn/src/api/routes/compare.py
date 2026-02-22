from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
import boto3
import logging
import json
from src.core.comparator.alignment import ComparatorEngine
from src.core.data.formatter import DatasetBuilder
from src.infrastructure.s3_datasets import S3DatasetGateway
from src.core.comparator.entity_extractor import HotfixDetector
from src.infrastructure.clients.config_client import TenantConfigClient
from src.infrastructure.redis_notifier import EventPublisher
from src.infrastructure.queue_manager import QueueManager
from src.orchestration.job_scheduler import JobScheduler
from src.db.database import SessionLocal
import redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/learning", tags=["Comparison"])


# Dependencia S3
def get_s3_client():
    return boto3.client('s3')

class CompareRequest(BaseModel):
    generated_artifact_ref: str # s3://...
    final_artifact_ref: str # s3://...
    tenant_id: str
    session_metadata: dict

@router.post("/compare")
async def trigger_comparison(
    req: CompareRequest, 
    background_tasks: BackgroundTasks,
    s3 = Depends(get_s3_client)
):
    """
    Endpoint asíncrono para iniciar la comparación forense de documentos.
    Resuelve el delta entre lo que la IA propuso y lo que el humano corrigió.
    """
    engine = ComparatorEngine(s3)
    
    # Iniciar pipeline en segundo plano
    background_tasks.add_task(run_comparison_job, engine, req)
    
    return {
        "status": "accepted", 
        "message": "Comparison job queued successfully",
        "tenant_id": req.tenant_id
    }

async def run_comparison_job(engine: ComparatorEngine, req: CompareRequest):
    """Worker de ejecución real que orquesta comparación, generación de datos y hotfixes"""
    try:
        # 1. Comparar documentos para obtener deltas
        report = engine.compare_documents(
            req.generated_artifact_ref,
            req.final_artifact_ref,
            req.tenant_id
        )
        
        # 2. Construir Dataset de Entrenamiento a partir de los deltas
        db = SessionLocal()
        queue_manager = QueueManager(db)
        dataset_builder = DatasetBuilder()
        enqueued_count = 0
        
        for delta in report.get("deltas", []):
            row = dataset_builder.build_training_row(delta)
            if row:
                queue_manager.enqueue_example(req.tenant_id, row)
                enqueued_count += 1
        
        # 3. Evaluar si se debe disparar un entrenamiento automático
        if enqueued_count > 0:
            logger.info(f"Encolados {enqueued_count} ejemplos para Tenant {req.tenant_id}")
            r_client = redis.from_url("redis://redis:6379/0")
            scheduler = JobScheduler(db, r_client)
            scheduler.evaluate_trigger(req.tenant_id)
        else:
            logger.info(f"No se generaron datos de entrenamiento útiles para el trabajo {report.get('job_id')}")

        db.close()

        # 4. Detección de Hotfixes (Aprender nombres en tiempo real)
        hotfix_detector = HotfixDetector()
        new_fixes = hotfix_detector.detect_hotfixes(report)
        
        if new_fixes:
            # A. Persistir en Config Service
            config_client = TenantConfigClient()
            success = await config_client.update_dictionary(req.tenant_id, new_fixes)
            
            if success:
                # B. Notificar a CORE en tiempo real vía Redis
                publisher = EventPublisher()
                await publisher.publish_hotfix(req.tenant_id, new_fixes)

        # 5. Persistir el reporte crudo también (para auditoría/stats)
        s3 = boto3.client('s3')
        report_key = f"learning_data/reports/{req.tenant_id}/{report['job_id']}.json"
        s3.put_object(
            Bucket="astra-models",
            Key=report_key,
            Body=json.dumps(report, indent=2),
            ContentType="application/json"
        )
        
    except Exception as e:
        logger.error(f"Fallo crítico en job de comparación: {e}")
