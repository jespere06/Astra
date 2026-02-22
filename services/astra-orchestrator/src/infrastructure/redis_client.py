import redis.asyncio as redis
from src.config import settings
import logging

logger = logging.getLogger(__name__)

# Configuración del Pool con resiliencia integrada
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
    socket_timeout=2.0,      # Evita bloquear el event loop de FastAPI
    socket_connect_timeout=2.0,
    retry_on_timeout=True
)

def get_redis() -> redis.Redis:
    """Inyectable para FastAPI"""
    return redis.Redis(connection_pool=redis_pool)
