import httpx
import logging
from typing import Dict, Any
from src.config import settings

logger = logging.getLogger(__name__)

class GuardServiceClient:
    def __init__(self):
        self.url = f"{settings.ASTRA_GUARD_URL}/v1/seal"
        self.headers = {
            "X-Service-Key": settings.ASTRA_INTERNAL_SERVICE_KEY
        }
        # Timeout extendido para archivos grandes (10s conexión, 30s lectura)
        self.timeout = httpx.Timeout(10.0, read=30.0)

    async def request_document_sealing(
        self, 
        tenant_id: str, 
        session_id: str, 
        file_content: bytes, 
        filename: str = "acta.docx"
    ) -> Dict[str, Any]:
        """
        Envía el binario a GUARD para generar el hash de integridad y el sello.
        """
        files = {
            "file": (filename, file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        data = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "builder_version": "1.0-astra-native"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info(f"🛡️ Solicitando sellado para sesión {session_id}...")
                response = await client.post(
                    self.url,
                    data=data,
                    files=files,
                    headers=self.headers
                )
                
                if response.status_code == 201 or response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Documento sellado exitosamente. Hash: {result.get('integrity_hash', 'unknown')}")
                    return result
                
                logger.error(f"❌ GUARD rechazó el sellado: {response.status_code} - {response.text}")
                # Raise specific exception so caller knows it's integrity failure
                raise Exception(f"INTEGRITY_SERVICE_REJECTION: {response.status_code}")

            except httpx.RequestError as e:
                logger.error(f"❌ Error de comunicación con ASTRA-GUARD: {e}")
                # Raise specific exception for retry logic potential
                raise Exception("INTEGRITY_SERVICE_UNREACHABLE")
