import httpx
import logging
from src.config import settings
from src.services.guard_client import GuardServiceClient

logger = logging.getLogger(__name__)

class OrchestrationService:
    @staticmethod
    async def finalize_and_seal(payload: dict) -> dict:
        guard_client = GuardServiceClient()
        
        async with httpx.AsyncClient() as client:
            # 1. Paso: BUILDER (Construcción)
            logger.info(f"🏗️ Iniciando construcción para sesión {payload.get('session_id')}")
            try:
                builder_res = await client.post(
                    f"{settings.BUILDER_URL}/v1/builder/generate",
                    json=payload,
                    timeout=60.0 # El build puede ser lento
                )
                builder_res.raise_for_status()
                builder_data = builder_res.json()
            except Exception as e:
                logger.error(f"Builder failed: {e}")
                # Re-raise to abort process
                raise e
            
            # 2. Paso Intermedio: Recuperar el binario generado
            # El Builder retorna una URL, debemos descargar los bytes para pasarlos a Guard
            docx_url = builder_data.get("download_url")
            
            # If docx_url is mock or local, we need to handle it. 
            # In Dev, if builder_client returns mock URL, we might fail to fetch if not real.
            # Assuming real URL or reachable internal URL.
            
            try:
                if "mock" in docx_url and settings.ENVIRONMENT == "development":
                     # Simulate content for dev to avoid 404 on mock S3 url
                     binary_content = b"Mock Content for Development Sealing"
                else:
                    docx_response = await client.get(docx_url)
                    docx_response.raise_for_status()
                    binary_content = docx_response.content
            except Exception as e:
                logger.error(f"Failed to retrieve document content from {docx_url}: {e}")
                # If we cannot get the document, we cannot seal it. 
                raise Exception("DOCUMENT_RETRIEVAL_FAILED")

            # 3. Paso: GUARD (Sellado e Integridad)
            # BLOQUEANTE: Si esto falla, el orquestador no retorna éxito al cliente
            # Guard raises exception if fails, which aborts the flow (Controller catches 500)
            seal_result = await guard_client.request_document_sealing(
                tenant_id=payload.get("tenant_id"),
                session_id=payload.get("session_id"),
                file_content=binary_content
            )

            # 4. Respuesta Consolidada
            return {
                "download_url": docx_url,
                "integrity_hash": seal_result.get("integrity_hash"),
                "seal_id": seal_result.get("seal_id"),
                "timestamp": seal_result.get("timestamp"),
                "status": "FINALIZED_AND_SEALED"
            }
