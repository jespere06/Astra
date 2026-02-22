import json
from typing import List, Dict, Any, Optional
from redis.asyncio import Redis
from src.config import settings

class SessionStore:
    def __init__(self, redis: Redis):
        self.redis = redis
        # Usar configuración para TTL
        self.ttl = settings.SESSION_TTL_SECONDS 

    def _meta_key(self, session_id: str) -> str:
        return f"session:{session_id}:meta"

    def _blocks_key(self, session_id: str) -> str:
        return f"session:{session_id}:blocks"

    async def start_session(self, session_id: str, metadata: Dict[str, Any]):
        """Persiste la metadata inicial de la sesión"""
        key = self._meta_key(session_id)
        serialized_meta = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) 
                           for k, v in metadata.items()}
        
        async with self.redis.pipeline() as pipe:
            await pipe.hset(key, mapping=serialized_meta)
            await pipe.expire(key, self.ttl)
            await pipe.execute()

    async def append_block(self, session_id: str, sequence_id: int, block_data: Dict[str, Any]):
        """Inserta un bloque y refresca TTL (Touch)"""
        key = self._blocks_key(session_id)
        meta_key = self._meta_key(session_id)
        
        block_json = json.dumps(block_data)
        
        async with self.redis.pipeline() as pipe:
            await pipe.zadd(key, {block_json: sequence_id})
            # Refresh TTL para ambas llaves (Actividad de sesión)
            await pipe.expire(key, self.ttl)
            await pipe.expire(meta_key, self.ttl)
            await pipe.execute()

    async def get_full_session_data(self, session_id: str) -> Dict[str, Any]:
        meta_key = self._meta_key(session_id)
        blocks_key = self._blocks_key(session_id)

        async with self.redis.pipeline() as pipe:
            pipe.hgetall(meta_key)
            pipe.zrange(blocks_key, 0, -1)
            # Lectura NO refresca TTL automáticamente para no sobrecargar Redis en polling,
            # pero el cliente puede llamar a touch si es necesario.
            results = await pipe.execute()

        meta = results[0]
        if not meta:
            return None

        blocks = [json.loads(b) for b in results[1]]
        
        return {
            "metadata": meta,
            "blocks": blocks
        }

    async def update_session_context(self, session_id: str, updates: Dict[str, Any]):
        """Actualiza campos parciales del contexto y refresca TTL"""
        key = self._meta_key(session_id)
        
        data_to_set = {}
        for k, v in updates.items():
            if v is not None:
                if isinstance(v, bool):
                    data_to_set[k] = "true" if v else "false"
                else:
                    data_to_set[k] = str(v)

        if data_to_set:
            async with self.redis.pipeline() as pipe:
                await pipe.hset(key, mapping=data_to_set)
                await pipe.expire(key, self.ttl)
                await pipe.execute()

    async def get_current_context(self, session_id: str) -> Dict[str, Any]:
        key = self._meta_key(session_id)
        fields = ["current_speaker_id", "topic", "is_restricted"]
        values = await self.redis.hmget(key, fields)
        
        return {
            "current_speaker_id": values[0] or "UNKNOWN",
            "topic": values[1] or "GENERAL",
            "is_restricted": values[2] == "true"
        }

    async def update_block_status(self, session_id: str, sequence_id: int, updates: Dict[str, Any]):
        key = self._blocks_key(session_id)
        
        current_members = await self.redis.zrangebyscore(key, min=sequence_id, max=sequence_id)
        
        if not current_members:
            return 
            
        old_block_json = current_members[0]
        try:
           block_data = json.loads(old_block_json)
        except json.JSONDecodeError:
           return
           
        block_data.update(updates)
        new_block_json = json.dumps(block_data)
        
        if old_block_json != new_block_json:
            async with self.redis.pipeline() as pipe:
                await pipe.zrem(key, old_block_json)
                await pipe.zadd(key, {new_block_json: sequence_id})
                # Refresh TTL en actualización de bloques (ej: recuperación worker)
                await pipe.expire(key, self.ttl)
                await pipe.execute()
