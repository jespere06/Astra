import json
import logging
import redis.asyncio as redis
from datetime import datetime

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self, redis_url: str = "redis://redis:6379/0"):
        self.redis_url = redis_url
        self.channel = "astra:events:intelligence"

    async def publish_hotfix(self, tenant_id: str, updates: dict):
        """
        Publica el evento de actualización de diccionario en Redis.
        """
        if not updates:
            return

        event = {
            "event": "DICTIONARY_UPDATED",
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "dictionary_delta": updates
        }
        
        try:
            r = redis.from_url(self.redis_url, decode_responses=True)
            await r.publish(self.channel, json.dumps(event))
            logger.info(f"📡 Evento DICTIONARY_UPDATED publicado para {tenant_id}")
            await r.aclose()
        except Exception as e:
            logger.error(f"Error publicando en Redis: {e}")
