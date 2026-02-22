"""
API Routes para Jobs de transcripción batch.

POST /v1/jobs       → Crear job (sube audio + despacha worker)
GET  /v1/jobs       → Listar jobs del tenant
GET  /v1/jobs/{id}  → Detalle de un job
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from redis.asyncio import Redis

from src.infrastructure.redis_client import get_redis
from src.infrastructure.storage_service import StorageService
from src.jobs.models import (
    CreateJobResponse,
    JobStatusResponse,
    JobListResponse,
)
from src.jobs.manager import JobManager
from src.jobs.store import JobStore
from src.middleware.auth import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/jobs", tags=["Batch Jobs"])

# Singleton de storage (reutiliza el existente)
_storage = StorageService()


def _get_manager(redis: Redis = Depends(get_redis)) -> JobManager:
    return JobManager(redis, _storage)


def _get_store(redis: Redis = Depends(get_redis)) -> JobStore:
    return JobStore(redis)


@router.post("", response_model=CreateJobResponse, status_code=201)
async def create_job(
    file: UploadFile = File(..., description="Archivo de audio a transcribir"),
    provider: str = Form("whisper", description="Motor: whisper | parakeet"),
    tenant_id: str = Depends(get_current_tenant),
    manager: JobManager = Depends(_get_manager),
):
    """
    Crea un nuevo job de transcripción batch.
    
    Sube el audio a S3 y despacha un worker GPU en RunPod.
    El resultado estará disponible vía GET /v1/jobs/{job_id} cuando el status sea COMPLETED.
    """
    # Leer contenido del audio
    content = await file.read()
    if not content:
        raise HTTPException(400, "El archivo de audio está vacío")

    # Límite de tamaño (500MB)
    max_bytes = 500 * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(413, f"Archivo excede el límite de {max_bytes // (1024*1024)}MB")

    job = await manager.submit_job(
        tenant_id=tenant_id,
        audio_content=content,
        filename=file.filename or "audio.wav",
        provider=provider,
    )

    return CreateJobResponse(
        job_id=job.id,
        status=job.status.value,
        message=f"Job despachado exitosamente. Provider: {job.provider}",
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant),
    store: JobStore = Depends(_get_store),
):
    """Consulta el estado y resultado de un job."""
    job = await store.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} no encontrado")
    if job.tenant_id != tenant_id:
        raise HTTPException(403, "No tienes acceso a este job")

    return JobStatusResponse(**job.model_dump())


@router.get("", response_model=JobListResponse)
async def list_jobs(
    offset: int = 0,
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
    store: JobStore = Depends(_get_store),
):
    """Lista los jobs del tenant (más reciente primero)."""
    if limit > 100:
        limit = 100

    jobs, total = await store.list_by_tenant(tenant_id, offset, limit)

    return JobListResponse(
        jobs=[JobStatusResponse(**j.model_dump()) for j in jobs],
        total=total,
    )
