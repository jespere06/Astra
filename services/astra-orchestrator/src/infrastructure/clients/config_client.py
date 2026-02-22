import httpx
import logging
from src.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ConfigClient:
    def __init__(self):
        self.base_url = settings.TENANT_CONFIG_URL
        self.timeout = httpx.Timeout(2.0)

    async def get_tenant_config(self, tenant_id: str) -> dict:
        """Recupera los mapeos y el modelo del inquilino"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/v1/config/{tenant_id}")
                if response.status_code == 404:
                    # Mocking config for now if service not reachable in dev
                    if settings.ENVIRONMENT == "development":
                        logger.warning(f"Config service not found, returning mock config for tenant {tenant_id}")
                        return {
                            "adapter_id": "base-model-v1",
                            "style_map": {"body": "Normal", "header": "Heading 1"},
                            "zone_map": {"DEFAULT": "Body"},
                            "table_map": {}
                        }
                    raise HTTPException(status_code=422, detail=f"Tenant {tenant_id} no configurado")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error conectando a Config Service: {e}")
                # Mocking config for now if service not reachable in dev
                if settings.ENVIRONMENT == "development":
                     logger.warning(f"Config service connection failed, returning mock config for tenant {tenant_id}")
                     return {
                        "adapter_id": "base-model-v1",
                        "style_map": {"body": "Normal", "header": "Heading 1"},
                        "zone_map": {"DEFAULT": "Body"},
                        "table_map": {}
                    }
                raise HTTPException(status_code=503, detail="Servicio de configuración no disponible")
