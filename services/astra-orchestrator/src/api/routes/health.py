from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from src.infrastructure.redis_client import get_redis

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check(redis: Redis = Depends(get_redis)):
    """Verifica el estado de los componentes críticos"""
    try:
        # Validación activa del socket de Redis
        await redis.ping()
        return {
            "status": "ok",
            "components": {
                "orchestrator": "up",
                "redis": "connected"
            }
        }
    except Exception as e:
        return Response(
            content='{"status": "degraded", "error": "Redis unreachable"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )
