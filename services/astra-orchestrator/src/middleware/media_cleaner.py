import hashlib
import logging
import uuid
from typing import Tuple
from src.config import settings
from src.infrastructure.grpc.ingest_client import IngestGrpcClient
from src.logic.image_processor import ImageNormalizer

logger = logging.getLogger(__name__)

class MediaOptimizationService:
    def __init__(self):
        self.ingest_client = IngestGrpcClient()

    async def handle_upload(self, tenant_id: str, raw_content: bytes) -> Tuple[str, bytes, bool]:
        """
        Ejecuta el Asset Loop:
        1. Deduplicación (gRPC Fail-Open).
        2. Optimización (Si es nuevo).
        
        Returns:
            (asset_id, content_to_store, is_duplicate)
        """
        # 1. Deduplication using Raw Content
        # We send raw content hash/check to ingest to see if identical file exists
        is_dup, remote_asset_id, confidence = await self.ingest_client.check_duplicate(
            tenant_id, raw_content
        )

        if is_dup and remote_asset_id:
            logger.info(f"♻️ Activo duplicado detectado (ID: {remote_asset_id}). Ahorrando almacenamiento.")
            # If duplicated, we don't store new content, so return raw (caller won't use it for storage if is_dup is True)
            return remote_asset_id, raw_content, True

        # 2. Si es nuevo -> Optimizar (Ruta 7 - Optimización)
        new_asset_id = str(uuid.uuid4())
        
        # Normalizar para almacenamiento eficiente
        optimized_content = ImageNormalizer.process(raw_content)
        
        if len(raw_content) > 0:
            compression_ratio = (1 - (len(optimized_content) / len(raw_content))) * 100
            logger.info(f"📸 Imagen optimizada. Ahorro: {compression_ratio:.2f}%")

        return new_asset_id, optimized_content, False
