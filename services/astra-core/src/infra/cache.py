import asyncio
import json
import logging
import os
try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from src.config import get_settings
from src.services.model_manager import IntelligenceReloader

logger = logging.getLogger(__name__)

class RedisEventListener:
    def __init__(self):
        self.settings = get_settings()
        if redis:
            # Construir URL de Redis (usando host de docker o env var)
            # Asumimos que QDRANT_HOST y REDIS comparten red, o usamos variable explícita
            redis_host = os.getenv("REDIS_HOST", "localhost")
            self.redis = redis.from_url(
                f"redis://{redis_host}:6379/0", 
                decode_responses=True
            )
        else:
            self.redis = None
        self.reloader = IntelligenceReloader()
        self.running = False

    async def start(self):
        if not self.redis:
            logger.warning("Redis client not installed. Event listener disabled.")
            return

        self.running = True
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.settings.REDIS_EVENT_CHANNEL)
            logger.info(f"👂 Escuchando eventos de inteligencia en: {self.settings.REDIS_EVENT_CHANNEL}")

            async for message in pubsub.listen():
                if not self.running:
                    break
                
                if message["type"] == "message":
                    # Procesar evento en background para no bloquear el loop de escucha
                    asyncio.create_task(self._handle_event(message["data"]))
                    
        except Exception as e:
            logger.error(f"Error en listener Redis: {e}")
            # Lógica de reconexión básica
            await asyncio.sleep(5)
            if self.running:
                asyncio.create_task(self.start()) # Reiniciar

    async def stop(self):
        self.running = False
        if self.redis:
            await self.redis.close()

    async def _handle_event(self, data_str: str):
        try:
            payload = json.loads(data_str)
            event_type = payload.get("event")
            tenant_id = payload.get("tenant_id")

            if not tenant_id:
                return

            if event_type == "MODEL_UPDATED":
                # Payload: { "event": "MODEL_UPDATED", "tenant_id": "...", "s3_uri": "...", "version": "..." }
                s3_uri = payload.get("s3_uri")
                version = payload.get("version")
                
                if s3_uri and version:
                    await self.reloader.swap_adapter(tenant_id, s3_uri, version)

            elif event_type == "DICTIONARY_UPDATED":
                # Payload: { "event": "...", "tenant_id": "...", "dictionary_delta": {...} }
                new_entries = payload.get("dictionary_delta", {})
                
                # Obtener diccionario actual y mezclar
                current = self.reloader.get_dictionary(tenant_id)
                current.update(new_entries)
                
                self.reloader.update_dictionary(tenant_id, current)

        except json.JSONDecodeError:
            logger.warning("Evento Redis recibido con formato JSON inválido")
        except Exception as e:
            logger.error(f"Error procesando evento de hot-reload: {e}")