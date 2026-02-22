from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, status, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from src.schemas.session_dtos import SessionStartRequest, SessionState, SessionContextUpdate, CurrentContextResponse
from src.services.session_service import SessionService
from src.services.processor import IngestProcessor
from src.services.finalizer import SessionFinalizer
from src.services.orchestration_service import OrchestrationService
from src.services.cleanup import CleanupService
from src.infrastructure.redis_client import get_redis
from src.infrastructure.redis_lock import SessionLock
from src.models.session_store import SessionStore
from src.infrastructure.clients.config_client import ConfigClient
from src.infrastructure.storage_service import StorageService

router = APIRouter(prefix="/v1/session", tags=["Session"])

def get_session_containers(redis=Depends(get_redis)):
    store = SessionStore(redis)
    config_client = ConfigClient()
    storage_service = StorageService()
    
    session_service = SessionService(store, config_client)
    ingest_processor = IngestProcessor(store, storage_service)
    
    return session_service, ingest_processor

@router.post(
    "/start", 
    response_model=SessionState, 
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar Nueva Sesión",
    description="Inicializa una sesión congelando la configuración del tenant y estableciendo el esqueleto del acta.",
    responses={
        401: {"description": "No autorizado o token inválido"},
        502: {"description": "Error conectando con Tenant Config Service"}
    }
)
async def start_session(
    request: SessionStartRequest,
    containers = Depends(get_session_containers)
):
    service, _ = containers
    return await service.start_new_session(request)

@router.patch(
    "/{session_id}/current-context", 
    response_model=CurrentContextResponse,
    summary="Actualizar Contexto Dinámico",
    description="Modifica metadatos volátiles como el orador actual o el tema en discusión.",
    responses={
        404: {"description": "Sesión no encontrada o cerrada"}
    }
)
async def update_session_context(
    session_id: str,
    request: SessionContextUpdate,
    containers = Depends(get_session_containers)
):
    service, _ = containers
    return await service.update_context(session_id, request)

@router.post(
    "/{session_id}/append", 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Anexar Chunk de Audio",
    description="Recibe un fragmento de audio (WAV/MP3) para procesamiento asíncrono. Retorna 'block_id' para tracking.",
    responses={
        400: {"description": "Formato de audio inválido"},
        413: {"description": "Chunk excede tamaño máximo (5MB)"}
    }
)
async def append_audio_chunk(
    session_id: str,
    file: UploadFile = File(...),
    sequence_id: int = Form(...),
    containers = Depends(get_session_containers)
):
    _, processor = containers
    audio_bytes = await file.read()
    block_id = await processor.process_chunk(session_id, sequence_id, audio_bytes)
    
    return {"status": "accepted", "block_id": block_id}

@router.post(
    "/{session_id}/finalize",
    summary="Finalizar y Sellado",
    description="Cierra la sesión, ensambla los bloques y solicita el sellado criptográfico. Si hay bloques pendientes ('Draining'), retorna 202.",
    responses={
        200: {"description": "Sesión finalizada y documento generado"},
        202: {"description": "En draining: Hay audios procesándose, intentar de nuevo en unos segundos"},
        409: {"description": "Conflicto: Ya hay un proceso de finalización en curso"}
    }
)
async def finalize_session(
    session_id: str, 
    background_tasks: BackgroundTasks,
    redis=Depends(get_redis)
):
    lock = SessionLock(redis)
    store = SessionStore(redis)
    storage = StorageService()
    finalizer = SessionFinalizer(store, storage)
    cleanup_service = CleanupService() # Instancia local

    # 1. Lock de Concurrencia
    if not await lock.acquire(session_id):
        raise HTTPException(status_code=409, detail="Proceso de finalización ya en curso")

    try:
        # 2. Control de Draining
        if await finalizer.check_draining_status(session_id):
            await lock.release(session_id)
            return JSONResponse(status_code=202, content={"is_draining": True})

        # 3. Ejecutar Construcción y Sellado
        payload = await finalizer.prepare_payload(session_id)
        result = await OrchestrationService.finalize_and_seal(payload)
        
        # 4. Archivados y Limpieza
        # Marcar sesión como cerrada en Redis (El TTL se encargará de borrarla eventualmente)
        await store.update_session_context(session_id, {"status": "CLOSED"})
        
        # Tarea de fondo: Limpiar basura en S3 (Fire-and-Forget)
        background_tasks.add_task(cleanup_service.purge_session_resources, session_id)
        
        return result
    finally:
        await lock.release(session_id)

@router.post(
    "/{session_id}/clone", 
    status_code=201,
    summary="Clonar Sesión (V2)",
    description="Crea una nueva sesión vacía copiando la metadata de una existente. Útil para correcciones legales posteriores."
)
async def clone_session(session_id: str, redis=Depends(get_redis)):
    store = SessionStore(redis)
    
    v1_state = await store.get_session_state(session_id)
    if not v1_state:
        raise HTTPException(status_code=404, detail="Session not found")
        
    new_session_id = str(uuid.uuid4())
    v2_meta = v1_state.model_dump()
    v2_meta.update({
        "session_id": new_session_id,
        "status": "OPEN",
        "parent_session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    await store.start_session(new_session_id, v2_meta)
    
    return {"new_session_id": new_session_id, "parent_session_id": session_id}
