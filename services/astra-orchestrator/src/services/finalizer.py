import logging
import json
import sys
from typing import Dict, Any, List, Optional
from src.config import settings
from src.models.session_store import SessionStore
from src.infrastructure.storage_service import StorageService
from src.infrastructure.clients.builder_client import BuilderClient
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SessionFinalizer:
    def __init__(self, store: SessionStore, storage: StorageService):
        self.store = store
        self.storage = storage
        self.builder_client = BuilderClient()
        # Ensure handover bucket exists
        self.storage._ensure_bucket(settings.S3_HANDOVER_BUCKET)

    async def check_draining_status(self, session_id: str) -> bool:
        """Verifica si hay bloques que aún se están procesando en CORE"""
        full_data = await self.store.get_full_session_data(session_id)
        for block in full_data.get("blocks", []):
            if isinstance(block, str): # Handle Redis string blobs if store returned raw
                 block = json.loads(block)
            if block.get("status") == "PROCESSING":
                return True
        return False

    async def prepare_payload(self, session_id: str) -> Dict[str, Any]:
        """Ensambla, reordena y aplica el patrón Claim Check"""
        # Retrieve full data
        full_data = await self.store.get_full_session_data(session_id)
        if not full_data:
             raise HTTPException(status_code=404, detail="Session not found")
        
        meta = full_data["metadata"]
        raw_blocks = full_data["blocks"]
        
        # Parse blocks if they are strings (Store implementation detail)
        blocks = []
        for b in raw_blocks:
            if isinstance(b, str):
                blocks.append(json.loads(b))
            else:
                blocks.append(b)

        # 1. Reordenamiento Lógico por sequence_id
        blocks = sorted(blocks, key=lambda x: x.get("sequence_id", 0))
        
        # 2. Validación de Integridad de Secuencia (Fase3-T05.2)
        # Ignoramos sequence 0 (notas de sistema) para la validación de huecos
        actual_sequences = [b["sequence_id"] for b in blocks if b.get("sequence_id", 0) > 0]
        if actual_sequences:
            expected_range = list(range(min(actual_sequences), max(actual_sequences) + 1))
            if len(actual_sequences) != len(expected_range):
                logger.warning(f"Sesión {session_id}: Se detectaron huecos en la secuencia de audio.")

        # Parse Pinned Config
        pinned_config = meta.get("pinned_config")
        if isinstance(pinned_config, str):
            pinned_config = json.loads(pinned_config)
            
        s3_version_id = pinned_config.get("s3_version_id") if pinned_config else None

        # 3. Decisión de Handover (S3 vs Inline)
        payload_base = {
            "session_id": session_id,
            "tenant_id": meta.get("tenant_id"),
            "skeleton_id": meta.get("skeleton_id"),
            "skeleton_version_id": s3_version_id,
            "client_timezone": meta.get("client_timezone"),
            "pinned_config": pinned_config,
            "metadata": meta
        }
        
        # Calculate size of blocks JSON payload roughly
        blocks_json = json.dumps(blocks)
        if len(blocks_json.encode('utf-8')) > settings.HANDOVER_THRESHOLD_BYTES:
            
            # Construct JSON for handover including blocks
            handover_payload = payload_base.copy()
            handover_payload["blocks"] = blocks
            
            s3_ref = await self.storage.upload_session_dump(
                session_id, json.dumps(handover_payload)
            )
            
            # Return ref-only payload for builder
            return {
                **payload_base,
                "blocks": None,
                "session_ref": s3_ref
            }
        
        # Return full payload
        return {
            **payload_base,
            "blocks": blocks,
            "session_ref": None
        }

    async def finalize_session(self, session_id: str) -> str:
        # Legacy method kept for compatibility if needed, using new logic internally
        # But controller logic overrides this in next step.
        # Keeping it minimal or deprecating.
        return "" 
