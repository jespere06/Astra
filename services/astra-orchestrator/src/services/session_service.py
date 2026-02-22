import uuid
import logging
from datetime import datetime, timezone
from src.infrastructure.clients.config_client import ConfigClient
from src.models.session_store import SessionStore
from src.schemas.session_dtos import SessionStartRequest, SessionState, SessionContextUpdate, CurrentContextResponse

from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self, store: SessionStore, config_client: ConfigClient):
        self.store = store
        self.config_client = config_client

    async def update_context(self, session_id: str, update_data: SessionContextUpdate) -> CurrentContextResponse:
        """Lógica de negocio para actualización de contexto"""
        # 1. Verificar existencia de metadata básica
        # Optimization: We check existence by trying to get context. If empty/default, session might not exist.
        # But better to check explicit existence if needed. 
        # For MVP, we proceed. If session doesn't exist, keys are created (loose) or we check meta.
        # Let's check meta existence via get_full for correctness as per plan.
        
        # We need a lightweight existence check in Store, but get_full works.
        session_data = await self.store.get_full_session_data(session_id)
        if not session_data:
             raise HTTPException(status_code=404, detail="Session not found")
        
        meta = session_data["metadata"]
        if meta.get("status") != "OPEN":
            raise HTTPException(
                status_code=400, 
                detail=f"No se puede actualizar el contexto en una sesión con estado: {meta.get('status')}"
            )

        # 2. Persistir cambios en Redis
        await self.store.update_session_context(session_id, update_data.model_dump())
        
        # 3. Recuperar estado final consolidado
        updated_ctx = await self.store.get_current_context(session_id)
        return CurrentContextResponse(**updated_ctx)

    async def start_new_session(self, request: SessionStartRequest) -> SessionState:
        session_id = str(uuid.uuid4())
        
        # 1. Recuperar Configuración Actual del Inquilino
        config = await self.config_client.get_tenant_config(request.tenant_id)
        
        # 2. Version Pinning: S3 Version ID (Simulación de HeadObject)
        # En producción: s3_client.head_object(Bucket=..., Key=request.skeleton_id)['VersionId']
        s3_version_id = "v2026.02.13.001" 
        
        # 3. Check de modelo nuevo en LEARN (vía Redis Flag)
        adapter_id = config.get("adapter_id", "base-model-v1")
        new_model_flag = await self.store.redis.get(f"NEW_MODEL_AVAILABLE:{request.tenant_id}")
        if new_model_flag:
            adapter_id = new_model_flag
            logger.info(f"Sesión {session_id} usará adaptador actualizado: {adapter_id}")

        # 4. Construir Pinned Config (El contrato inmutable)
        pinned = {
            "s3_version_id": s3_version_id,
            "adapter_id": adapter_id,
            "style_map": config.get("style_map", {}),
            "zone_map": config.get("zone_map", {}),
            "table_map": config.get("table_map", {})
        }

        # 5. Estado Maestro
        session_meta = {
            "session_id": session_id,
            "tenant_id": request.tenant_id,
            "status": "OPEN",
            "skeleton_id": request.skeleton_id,
            "client_timezone": request.client_timezone,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pinned_config": pinned
        }

        # 6. Persistencia Atómica en Redis
        await self.store.start_session(session_id, session_meta)
        
        return SessionState(**session_meta)
