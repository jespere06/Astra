import logging
from src.infrastructure.storage_service import StorageService
from src.config import settings

logger = logging.getLogger(__name__)

class CleanupService:
    def __init__(self):
        self.storage = StorageService()

    async def purge_session_resources(self, session_id: str):
        """
        Ejecuta la limpieza "Fire-and-Forget" de recursos temporales en S3.
        No elimina assets (imágenes) ya que pueden ser deduplicados y usados por otros.
        Solo elimina:
        1. Audio de Failover (Chunks subidos cuando la IA falló).
        2. Dumps de Handover (JSONs grandes pasados al Builder).
        """
        logger.info(f"🗑️ Iniciando purga de recursos temporales para sesión {session_id}...")
        
        try:
            # 1. Limpiar Audio de Failover
            # Prefijo definido en processor.py: failover/{session_id}/
            await self.storage.delete_prefix(
                bucket=settings.S3_FAILOVER_BUCKET,
                prefix=f"failover/{session_id}/"
            )

            # 2. Limpiar JSON Dumps de Handover
            # Prefijo definido en finalizer.py: dumps/{session_id}/
            await self.storage.delete_prefix(
                bucket=settings.S3_HANDOVER_BUCKET,
                prefix=f"dumps/{session_id}/"
            )
            
            logger.info(f"✅ Purga completada para sesión {session_id}")
            
        except Exception as e:
            # Loguear error pero no detener la ejecución (ya que es tarea de fondo)
            logger.error(f"⚠️ Error durante la purga de sesión {session_id}: {str(e)}")
