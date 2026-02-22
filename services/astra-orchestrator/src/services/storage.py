import uuid
import imghdr
import logging
from src.config import settings
from src.middleware.media_cleaner import MediaOptimizationService
from src.models.session_store import SessionStore
from src.infrastructure.storage_service import StorageService

logger = logging.getLogger(__name__)

class AssetService:
    def __init__(self, store: SessionStore):
        self.store = store
        self.media_service = MediaOptimizationService()
        self.storage = StorageService() 
        self.storage._ensure_bucket(settings.S3_BUCKET_ASSETS)

    async def process_asset_upload(self, session_id: str, file_name: str, content: bytes) -> dict:
        # 1. Validación de Seguridad: Magic Bytes
        file_type = imghdr.what(None, h=content)
        if file_type not in ['jpeg', 'png', 'jpg']:
             # Strict check: only allow image uploads that match normalizer support or allowed types
             # Prompt config ALLOWED_IMAGE_TYPES used strings "image/jpeg", here imghdr returns extensions.
             # We align with prompt request logic for file type check.
             # Prompt logic: "if file_type not in ['jpeg', 'png', 'jpg']"
            raise ValueError(f"Formato de imagen no permitido: {file_type}")

        session_data = await self.store.get_full_session_data(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        meta = session_data["metadata"]
        tenant_id = meta["tenant_id"]
        
        # 2. Delegar al Middleware de Optimización/Deduplicación
        asset_id, final_content, is_dup = await self.media_service.handle_upload(
            tenant_id, content
        )

        # 3. Lógica de S3
        if is_dup:
            # Construir URL lógica apuntando al asset existente (manejado por Ingest)
            s3_url = f"s3://{settings.S3_BUCKET_ASSETS}/{tenant_id}/{asset_id}"
        else:
            # Subir el contenido OPTIMIZADO
            # Forzamos extensión .jpg porque el normalizador convierte a JPEG
            safe_name = f"{uuid.uuid4()}.jpg"
            # Using _upload_to_s3 internal helper or generic upload
            s3_url = await self._upload_to_s3(tenant_id, asset_id, safe_name, final_content)

        # 4. Registrar en Redis como bloque IMAGE
        image_block = {
            "type": "IMAGE",
            "asset_id": asset_id,
            "s3_url": s3_url,
            "is_duplicate": is_dup,
            "target_placeholder": "ZONE_ANNEX", # Default ruteo para fotos
            "filename": file_name
        }
        
        await self.store.append_block(session_id, 0, image_block)

        return {
            "asset_id": asset_id,
            "s3_url": s3_url,
            "is_duplicate": is_dup
        }

    async def _upload_to_s3(self, tenant_id: str, asset_id: str, name: str, data: bytes):
        key = f"assets/{tenant_id}/{asset_id}/{name}"
        # Implementación delegada al driver S3 existente
        return await self.storage.upload_generic_file(settings.S3_BUCKET_ASSETS, key, data)
