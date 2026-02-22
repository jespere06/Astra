import logging
from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from redis.asyncio import Redis
from src.infrastructure.redis_client import get_redis
from src.infrastructure.job_repository import TrainingJobRepository
from src.schemas.job_dtos import TrainingJobRequest, JobResult, JobStatus
from src.models.training_job import TrainingJob
from src.services.processor import TrainingProcessor
from src.infrastructure.clients.mining_client import MiningClient
from src.jobs.runpod_client import RunPodClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/training", tags=["Training"])

def get_training_processor(redis: Redis = Depends(get_redis)):
    repo = TrainingJobRepository(redis)
    mining_client = MiningClient()
    runpod_client = RunPodClient()
    return TrainingProcessor(repo, mining_client, runpod_client), repo

@router.post("/train", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
async def trigger_training(
    request: TrainingJobRequest,
    background_tasks: BackgroundTasks,
    deps = Depends(get_training_processor)
):
    """
    Inicia un proceso de entrenamiento o validación de datos.
    
    Si config.execution_mode es 'DATA_PREP_ONLY', solo se realizará la minería y alineación.
    Si es 'FULL_TRAINING', se procederá al entrenamiento en RunPod tras la minería.
    """
    processor, repo = deps
    
    # 1. Crear el Job en estado PENDING
    job = TrainingJob(
        tenant_id=request.tenant_id,
        rows=request.rows,
        source_urls=request.source_urls,
        execution_mode=request.execution_mode,
        training_config=request.training_config or {}
    )
    await repo.create(job)
    
    # 2. Despachar el procesamiento en segundo plano
    background_tasks.add_task(processor.process_training_request, job.id, request)
    
    return JobResult(
        job_id=job.id,
        status=JobStatus.PENDING
    )

@router.get("/jobs/{job_id}", response_model=JobResult)
async def get_training_job_status(
    job_id: str,
    redis: Redis = Depends(get_redis)
):
    """
    Obtiene el estado y los resultados (si están disponibles) de un trabajo de entrenamiento.
    """
    repo = TrainingJobRepository(redis)
    job = await repo.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Trabajo {job_id} no encontrado")
    
    return JobResult(
        job_id=job.id,
        status=job.status,
        result_summary=job.result_summary,
        rows=job.rows
    )