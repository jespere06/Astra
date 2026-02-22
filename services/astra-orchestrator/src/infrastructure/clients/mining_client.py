import httpx
import logging
from typing import Dict, Any, List
from src.config import settings

logger = logging.getLogger(__name__)

class MiningClient:
    def __init__(self):
        # Apunta al puerto donde corre astra-ingest
        self.base_url = "http://localhost:8003" 
        self.timeout = 600.0 # 10 minutos

    async def run_mining_pipeline(self, tenant_id: str, source_urls: List[str]) -> Dict[str, Any]:
        logger.info(f"🚀 [REAL] Solicitando minería a {self.base_url} para Tenant: {tenant_id}")
        
        payload = {
            "tenant_id": tenant_id,
            "file_urls": source_urls,
            "provider": "deepgram"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # CORRECCIÓN: Se agregó "/v1" antes de /ingest
                response = await client.post(
                    f"{self.base_url}/v1/ingest/mining/sync", 
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"✅ Minería completada. Stats: {data.get('alignment_stats')}")
                return data

            except Exception as e:
                logger.error(f"❌ Error comunicando con Ingest Service: {e}")
                raise e

    async def run_single_mining(self, tenant_id: str, video_url: str) -> Dict[str, Any]:
        """Procesa un solo video (Ideal para iterar y mostrar progreso visual)"""
        payload = {
            "tenant_id": tenant_id,
            "video_url": video_url,
            "provider": "deepgram"
        }
        
        # Timeout infinito porque un video puede tardar varios minutos
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.base_url}/v1/ingest/mining/single", 
                json=payload
            )
            response.raise_for_status()
            return response.json()

