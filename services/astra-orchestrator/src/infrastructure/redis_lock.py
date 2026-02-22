from redis.asyncio import Redis

class SessionLock:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def acquire(self, session_id: str, ttl: int = 60) -> bool:
        """Adquiere un lock exclusivo para la finalización (SET NX)"""
        lock_key = f"lock:finalize:{session_id}"
        # Retorna True si obtuvo el lock, False si ya existe
        return await self.redis.set(lock_key, "locked", ex=ttl, nx=True)

    async def release(self, session_id: str):
        """Libera el lock manualmente"""
        await self.redis.delete(f"lock:finalize:{session_id}")
