import httpx
import logging
from src.config import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CoreClient:
    def __init__(self):
        # ASTRA-CORE URL (e.g., http://astra-core:8002/v1/core)
        self.base_url = settings.CORE_URL # Needs to be added to config.py
        self.timeout = httpx.Timeout(5.0) # 5 seconds aggressive timeout as per plan

    async def process_audio_chunk(self, audio_bytes: bytes, tenant_id: str) -> Dict[str, Any]:
        """
        Sends audio to Core for transcription and intent classification.
        Returns: {
            "raw_text": str,
            "clean_text": str,
            "intent": str, # 'PLANTILLA' | 'LIBRE'
            "confidence": float,
            "metadata": dict
        }
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Prepare multipart upload
                files = {'file': ('chunk.wav', audio_bytes, 'audio/wav')}
                data = {'tenant_id': tenant_id}
                
                response = await client.post(f"{self.base_url}/process", files=files, data=data)
                response.raise_for_status()
                return response.json()
                
            except httpx.TimeoutException:
                logger.error("Timeout connecting to ASTRA-CORE")
                raise # Let service handle fallback
            except httpx.HTTPError as e:
                logger.error(f"Error from ASTRA-CORE: {e}")
                raise
