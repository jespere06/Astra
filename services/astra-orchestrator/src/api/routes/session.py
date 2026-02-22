from fastapi import APIRouter, Depends, HTTPException
from src.schemas.session_dtos import SessionStartRequest, SessionState
from src.infrastructure.redis_client import get_redis
from src.core.session_manager import SessionManager
from redis.asyncio import Redis

router = APIRouter(prefix="/v1/session", tags=["Session"])

def get_session_manager(redis: Redis = Depends(get_redis)) -> SessionManager:
    return SessionManager(redis)

@router.post("/start", response_model=SessionState, status_code=201)
async def start_session(
    request: SessionStartRequest,
    manager: SessionManager = Depends(get_session_manager)
):
    """
    Inicializa una sesión de transcripción. 
    Realiza el 'Version Pinning' de la configuración del tenant.
    """
    # Aquí iría validación de JWT para asegurar que el tenant_id coincide con el token
    return await manager.create_session(request)

@router.get("/{session_id}/status", response_model=SessionState)
async def get_session_status(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    return await manager.get_session_state(session_id)
