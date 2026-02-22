import uuid
import json
from datetime import datetime
from fastapi import HTTPException
from redis.asyncio import Redis
from src.config import settings
from src.schemas.session_dtos import SessionStartRequest, SessionState

class SessionManager:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _get_meta_key(self, session_id: str) -> str:
        return f"astra:session:{session_id}:meta"

    def _get_blocks_key(self, session_id: str) -> str:
        return f"astra:session:{session_id}:blocks"

    async def create_session(self, request: SessionStartRequest) -> SessionState:
        session_id = str(uuid.uuid4())
        
        # 1. Simulación: Consultar Tenant Config Service (Version Pinning)
        # En producción, esto es una llamada HTTP al servicio de configuración
        # para obtener el mapa de estilos vigente EN ESTE MOMENTO.
        mock_style_map = {"heading_1": "HEADING_1_CALI", "body": "NORMAL_CALI"}
        
        # 2. Construir Estado Inicial (Inmutable)
        session_data = {
            "session_id": session_id,
            "tenant_id": request.tenant_id,
            "status": "OPEN",
            "skeleton_id": request.skeleton_id,
            "client_timezone": request.client_timezone,
            "style_map": json.dumps(mock_style_map), # Serializado
            "created_at": datetime.utcnow().isoformat(),
            "metadata": json.dumps(request.metadata)
        }

        # 3. Guardar en Redis (Hash) con TTL
        key = self._get_meta_key(session_id)
        
        async with self.redis.pipeline() as pipe:
            await pipe.hset(key, mapping=session_data)
            await pipe.expire(key, settings.SESSION_TTL_SECONDS)
            await pipe.execute()

        # Decodificar para retornar el objeto
        # El SessionState espera un dict para style_map
        return SessionState(
            **{k: session_data[k] for k in session_data if k != "style_map" and k != "metadata"},
            style_map=mock_style_map,
            metadata=request.metadata
        )

    async def get_session_state(self, session_id: str) -> SessionState:
        key = self._get_meta_key(session_id)
        data = await self.redis.hgetall(key)
        
        if not data:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
            
        # Deserializar campos JSON
        if "style_map" in data:
            data["style_map"] = json.loads(data["style_map"])
        if "metadata" in data and data["metadata"]:
             # Manejar caso donde metadata pueda ser string vacio o null en redis
            try:
                data["metadata"] = json.loads(data["metadata"])
            except:
                data["metadata"] = {}
            
        return SessionState(**data)
